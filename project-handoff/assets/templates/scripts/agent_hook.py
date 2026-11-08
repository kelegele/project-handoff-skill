#!/usr/bin/env python3
"""Project-scoped lifecycle journal; never treats a turn ending as task completion."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta

EVENTS = {'SessionStart', 'UserPromptSubmit', 'Stop', 'Interrupt', 'SessionEnd'}


def resolve_project_root(start: Path, home: Path):
    """根解析契约（设计 §6.4）：从 start 逐级向上；每级先查 .agent-handoff.json 再查 .git；
    home 与文件系统根本身永不被当作项目。命中即返回该目录，未命中返回 None。"""
    d = start
    while True:
        if d == home or d == d.parent:
            return None
        if (d / '.agent-handoff.json').is_file():
            return d
        if (d / '.git').exists():
            return d
        d = d.parent


def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


def load_config(path: Path):
    """宽容读取：v1/v2 均有效，多余键保留；返回 (settings, None) 或 (None, 具体错误消息)。"""
    if not path.is_file():
        return None, f'配置文件不存在：{path.name}'
    try:
        settings = json.loads(path.read_text())
    except ValueError:
        return None, '配置不是合法 JSON，未做任何修改'
    if not isinstance(settings, dict):
        return None, '配置必须是 JSON 对象'
    if settings.get('version') not in (1, 2):
        return None, f"不支持的配置 version：{settings.get('version')!r}（仅支持 1 或 2）"
    if not isinstance(settings.get('enabled'), bool):
        return None, '配置缺少布尔型 enabled 字段'
    return settings, None


def write_config(root: Path, settings: dict) -> None:
    merged = dict(settings)
    merged['version'] = 2
    atomic_json(root / '.agent-handoff.json', merged)


def heartbeat_payload(pid, now: datetime) -> str:
    """单行 JSON：心跳为主，PID 仅附带（钩子进程短命，自身 PID 无判定价值）。"""
    return json.dumps({'heartbeat': now.isoformat(timespec='seconds'),
                       'pid': pid if isinstance(pid, int) else None}, ensure_ascii=False) + '\n'


def _lock_idle(lock: Path, now: datetime):
    """锁的闲置时长；空锁或无法解析返回 None（按陈旧处理）。"""
    try:
        lines = [line for line in lock.read_text().splitlines() if line.strip()]
        heartbeat = datetime.fromisoformat(json.loads(lines[-1])['heartbeat'])
        return now - heartbeat
    except (ValueError, IndexError, KeyError, TypeError):
        return None


def recover_orphans(runs_dir: Path, now: datetime, max_idle_minutes: int = 30):
    """心跳超时且未正常关闭的 run 标记中断并清锁；返回回收的 run_id 列表。"""
    recovered = []
    if not runs_dir.is_dir():
        return recovered
    for run in sorted(runs_dir.iterdir()):
        if not run.is_dir():
            continue
        lock, runtime_path = run / '.lock', run / 'runtime.json'
        if not lock.is_file() or not runtime_path.is_file():
            continue
        try:
            state = json.loads(runtime_path.read_text())
        except ValueError:
            continue
        if state.get('last_event') == 'SessionEnd':
            continue
        idle = _lock_idle(lock, now)
        if idle is not None and idle <= timedelta(minutes=max_idle_minutes):
            continue
        state.update(interrupted=True, runtime_status='已中断（孤儿回收），待接手',
                     updated_at=now.isoformat(timespec='seconds'),
                     orphan_recovered_at=now.isoformat(timespec='seconds'))
        atomic_json(runtime_path, state)
        lock.unlink()
        recovered.append(state.get('run_id', run.name))
    return recovered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--agent', required=True, choices=['Codex', 'ZCode', 'QwenWork'])
    args = parser.parse_args()
    event = json.load(sys.stdin)
    if not isinstance(event, dict) or not isinstance(event.get('cwd'), str):
        return
    cwd = Path(event['cwd']).resolve()
    ROOT = resolve_project_root(cwd, Path.home())
    if ROOT is None:
        return
    settings, config_error = load_config(ROOT / '.agent-handoff.json')
    if settings is None or settings.get('enabled') is not True:
        return
    name = event.get('hook_event_name')
    session = event.get('session_id')
    if name not in EVENTS or not isinstance(session, str) or not session:
        return
    now_dt = datetime.now().astimezone()
    now = now_dt.isoformat(timespec='seconds')
    key = hashlib.sha256(session.encode()).hexdigest()[:20]
    runs_dir = ROOT / 'docs/execution/agent-runs'
    if name == 'SessionStart':
        recover_orphans(runs_dir, now_dt)
    folder = runs_dir / f'{args.agent}-{key}'
    folder.mkdir(parents=True, exist_ok=True)
    # Per-session lock protects concurrent events; human notes are created once only.
    pid = event.get('pid')
    with (folder / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.truncate(0)
        lock.write(heartbeat_payload(pid, now_dt))
        runtime = folder / 'runtime.json'
        state = json.loads(runtime.read_text()) if runtime.exists() else {}
        state.update(agent=args.agent, session_id=session, updated_at=now,
                     last_event=name, business_status='待 Agent 核对，钩子不判断业务完成')
        state.setdefault('started_at', now)
        state.setdefault('run_id', f'{args.agent}-{key}')
        statuses = {'SessionStart': '会话已启动／恢复', 'UserPromptSubmit': '进行中',
                    'Stop': '回合结束，业务完成情况待核对',
                    'Interrupt': '已中断，待接手', 'SessionEnd': '会话已关闭，业务完成情况待核对'}
        state['runtime_status'] = statuses[name]
        turn_id = event.get('turn_id')
        if isinstance(turn_id, str):
            state['turn_id'] = turn_id
        atomic_json(runtime, state)
        # Whitelist metadata: never save prompt, response, commands or transcript contents.
        record = {k: state[k] for k in ['run_id', 'agent', 'updated_at', 'last_event', 'runtime_status']}
        with (folder / 'events.jsonl').open('a') as output:
            output.write(json.dumps(record, ensure_ascii=False) + '\n')
        handover = folder / 'handover.md'
        if not handover.exists():
            with handover.open('x') as note:
                note.write(f'''# Agent 交接记录

- 运行编号：{args.agent}-{key}（自动生成；业务任务沿用原编号）
- 负责 Agent：{args.agent}
- 创建时间：{now}（本地时间）
- 业务任务编号：待填写
- 目标与范围：待填写
- 对应任务文档／台账：待填写
- 业务状态：待核对
- 已完成与核验：待填写
- 产物与证据：待填写
- 未完成与阻塞：待填写
- 下一步：待填写
- 授权范围：按最新用户明确指令，不因钩子扩大授权

自动运行状态见 runtime.json；本文件由 Agent 补齐，钩子不会覆盖已有内容。
已有任务台账时填写入口和简短交接，不重复复制完整过程。
''')
    if name in {'SessionStart', 'UserPromptSubmit'}:
        context = (f'本项目自动运行记录已建立：{folder.relative_to(ROOT)}。'
                   '先读 AGENTS.md、HANDOVER.md 及对应任务台账；沿用业务任务编号。'
                   f'结束前更新对应任务记录和 {handover.relative_to(ROOT)} 的简短摘要／入口，'
                   '并同步 HANDOVER.md，最终回复附记录路径；自动运行状态不等于任务完成。')
        print(json.dumps({'hookSpecificOutput': {'hookEventName': name, 'additionalContext': context}}, ensure_ascii=False))
    elif name == 'Stop' and '待填写' in handover.read_text():
        print(json.dumps({'systemMessage': f'运行状态已保存；交接记录尚有待填写项：{handover.relative_to(ROOT)}。请补齐任务摘要或已有台账入口；本提示不代表业务验收。'}, ensure_ascii=False))
    else:
        print('{}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # A journal failure must never block unrelated work or reveal input data.
        print(f'Project handoff hook: recording failed ({type(exc).__name__}); task may continue.', file=sys.stderr)
        print('{}')
