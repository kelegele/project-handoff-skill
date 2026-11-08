#!/usr/bin/env python3
"""Project-scoped lifecycle journal; never treats a turn ending as task completion."""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
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


AGENTS_SECTION_MARKER = '## 多 Agent 交接'


def _templates_dir() -> Path:
    """模板目录：随资产分发（本文件位于 templates/scripts/ 之下，上一级即 templates）。"""
    return Path(__file__).resolve().parent.parent


def cmd_enable(root: Path) -> int:
    config_path = root / '.agent-handoff.json'
    if config_path.is_file():
        settings, err = load_config(config_path)
        if settings is None:
            print(err)
            print('未修改任何文件；请先修复或确认该配置后再启用。')
            return 2
    else:
        settings = {}  # 全新项目：缺失不等于损坏，按默认开启
    settings['enabled'] = True
    write_config(root, settings)
    changed = ['.agent-handoff.json（version 2，enabled: true）']
    agents_md = root / 'AGENTS.md'
    current = agents_md.read_text() if agents_md.is_file() else ''
    if AGENTS_SECTION_MARKER not in current:
        with agents_md.open('a') as f:
            if current and not current.endswith('\n'):
                f.write('\n')
            f.write((_templates_dir() / 'AGENTS.section.md').read_text())
        changed.append('AGENTS.md（追加「多 Agent 交接」段）')
    handover = root / 'HANDOVER.md'
    if not handover.exists():
        handover.write_text((_templates_dir() / 'HANDOVER.md').read_text())
        changed.append('HANDOVER.md（新建模板）')
    print('已启用项目交接。变更：')
    for line in changed:
        print(f'- {line}')
    print(f'验证：python3 {Path(__file__).resolve()} --doctor')
    return 0


def cmd_disable(root: Path) -> int:
    settings, err = load_config(root / '.agent-handoff.json')
    if settings is None:
        print(err)
        print('未修改任何文件。')
        return 2
    settings['enabled'] = False
    write_config(root, settings)
    print('已关闭项目交接：.agent-handoff.json enabled=false。')
    print('保留：AGENTS.md 交接段、HANDOVER.md、docs/execution/ 运行记录（均未删除）。')
    print('彻底移除：删除 .agent-handoff.json 与 docs/execution/，并自行删去 AGENTS.md 交接段。')
    return 0


def _git_head(root: Path) -> str:
    try:
        out = subprocess.run(['git', '-C', str(root), 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else '-'
    except Exception:
        return '-'


def _run_state(run: Path) -> dict:
    try:
        return json.loads((run / 'runtime.json').read_text())
    except (OSError, ValueError):
        return {}


def _handover_note(run: Path) -> str:
    """被归档 run 的一句话摘要：handover.md 第一个非标题非空行，截 80 字。"""
    try:
        for line in (run / 'handover.md').read_text().splitlines():
            s = line.strip()
            if s and not s.startswith('#'):
                return s[:80]
    except OSError:
        pass
    return '-'


def _rotate_runs(runs_dir: Path, keep_per_agent: int, min_per_agent: int,
                 index_max_lines: int, head: str) -> int:
    if not runs_dir.is_dir():
        return 0
    by_agent = {}
    for run in runs_dir.iterdir():
        if run.is_dir() and run.name != 'archive':
            by_agent.setdefault(run.name.split('-', 1)[0], []).append(run)
    archived, index_lines = 0, []
    for agent, dirs in by_agent.items():
        if len(dirs) <= keep_per_agent:
            continue
        dirs.sort(key=lambda d: _run_state(d).get('started_at', ''))
        droppable = len(dirs) - keep_per_agent
        allowed = droppable if len(dirs) - droppable >= min_per_agent \
            else max(len(dirs) - min_per_agent, 0)
        for run in dirs[:allowed]:
            state = _run_state(run)
            flag = '[中断] ' if state.get('interrupted') else ''
            index_lines.append(
                f"- {flag}{state.get('started_at', '-')} | {state.get('agent', agent)} | "
                f"{state.get('session_id', '-')} | {head} | {_handover_note(run)}")
            shutil.rmtree(run, ignore_errors=True)
            archived += 1
    if index_lines:
        archive_dir = runs_dir / 'archive'
        archive_dir.mkdir(parents=True, exist_ok=True)
        index = archive_dir / 'index.md'
        old = index.read_text().splitlines() if index.is_file() else []
        index.write_text('\n'.join((old + index_lines)[-index_max_lines:]) + '\n')
    return archived


def _compact_handover(root: Path, max_bytes: int, max_lines: int, keep_sections: int) -> str:
    handover = root / 'HANDOVER.md'
    if not handover.is_file():
        return ''
    text = handover.read_text()
    if len(text.encode()) <= max_bytes and len(text.splitlines()) <= max_lines:
        return ''
    preamble, sections, current = [], [], None
    for line in text.splitlines(keepends=True):
        if line.startswith('## '):
            current = [line]
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)
    if len(sections) <= keep_sections:
        return ''  # 无小节结构或小节太少：遗留内容一字不动
    moved, kept = sections[:-keep_sections], sections[-keep_sections:]
    archive_dir = root / 'docs' / 'execution' / 'handoff-archive'
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / (datetime.now().astimezone().strftime('%Y%m%d-%H%M%S') + '.md')
    archive.write_text('# 历史交接小节（--gc 归档）\n\n' + ''.join(''.join(s) for s in moved))
    pointer = (f'\n- 已归档 {len(moved)} 个历史小节：'
               f'docs/execution/handoff-archive/{archive.name}（agent 默认不读）\n')
    handover.write_text(''.join(preamble) + ''.join(''.join(s) for s in kept) + pointer)
    return archive.name


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) if path.is_dir() else 0


def _count_runs(runs_dir: Path) -> int:
    return sum(1 for d in runs_dir.iterdir()
               if d.is_dir() and d.name != 'archive') if runs_dir.is_dir() else 0


def cmd_gc(root: Path, keep_per_agent: int = 20, min_per_agent: int = 2,
           index_max_lines: int = 200, handover_max_bytes: int = 8192,
           handover_max_lines: int = 300, keep_sections: int = 3) -> int:
    exec_dir = root / 'docs' / 'execution'
    runs_dir = exec_dir / 'agent-runs'
    before_bytes, before_runs = _dir_size(exec_dir), _count_runs(runs_dir)
    recovered = recover_orphans(runs_dir, datetime.now().astimezone())
    head = _git_head(root)
    archived = _rotate_runs(runs_dir, keep_per_agent, min_per_agent, index_max_lines, head)
    compacted = _compact_handover(root, handover_max_bytes, handover_max_lines, keep_sections)
    handover = root / 'HANDOVER.md'
    print(f'--gc 完成：回收孤儿 {len(recovered)} 个；归档 run {archived} 个'
          f'（每 agent 保留 {keep_per_agent}，至少 {min_per_agent}）；'
          f'HANDOVER {"已瘦身（归档 " + compacted + "）" if compacted else "未变"}。')
    print(f'占用：docs/execution {before_bytes} → {_dir_size(exec_dir)} 字节；'
          f'run {before_runs} → {_count_runs(runs_dir)} 个；'
          f'HANDOVER {handover.stat().st_size if handover.is_file() else 0} 字节。')
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--agent', default=None, choices=['Codex', 'ZCode', 'QwenWork'])
    parser.add_argument('--enable', action='store_true')
    parser.add_argument('--disable', action='store_true')
    parser.add_argument('--gc', action='store_true')
    args = parser.parse_args()
    if args.enable or args.disable or args.gc:
        root = resolve_project_root(Path.cwd(), Path.home())
        if root is None:
            print('未找到项目根（向上未命中 .agent-handoff.json 或 .git），未做任何修改。')
            return 2
        if args.enable:
            return cmd_enable(root)
        if args.disable:
            return cmd_disable(root)
        return cmd_gc(root)
    if not args.agent:
        parser.error('事件模式需要 --agent；命令模式见 --enable / --disable')
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
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # A journal failure must never block unrelated work or reveal input data.
        print(f'Project handoff hook: recording failed ({type(exc).__name__}); task may continue.', file=sys.stderr)
        print('{}')
