"""GC rotation and HANDOVER compaction (design §8.2-8.3, Task 6)."""
import hashlib
import importlib.util
import json

from conftest import SCRIPT, make_project, run_cmd

spec = importlib.util.spec_from_file_location('agent_hook', SCRIPT)
agent_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_hook)


def seed_runs(p, agent='Codex', count=3, note_fmt='摘要 {i}'):
    runs = p / 'docs' / 'execution' / 'agent-runs'
    for i in range(count):
        rid = f'{agent}-run{i:02d}aaaaaaaaaaaaaaaaaa'
        run = runs / rid
        run.mkdir(parents=True)
        (run / 'runtime.json').write_text(json.dumps({
            'run_id': rid, 'agent': agent, 'session_id': f's-{i}',
            'started_at': f'2026-11-08T10:{i:02d}:00+08:00',
            'updated_at': f'2026-11-08T10:{i:02d}:30+08:00',
            'last_event': 'SessionEnd', 'runtime_status': '会话已关闭，业务完成情况待核对'}))
        (run / 'handover.md').write_text(
            f'# Agent 交接记录\n\n- 摘要：{note_fmt.format(i=i)}\n')
    return runs


def run_names(runs):
    return sorted(d.name for d in runs.iterdir() if d.is_dir() and d.name != 'archive')


def test_25_runs_archived_to_5(tmp_path):
    p = make_project(tmp_path)
    seed_runs(p, count=25)
    rc = agent_hook.cmd_gc(p)
    assert rc == 0
    assert len(run_names(p / 'docs' / 'execution' / 'agent-runs')) == 20
    index = (p / 'docs' / 'execution' / 'agent-runs' / 'archive' / 'index.md')
    lines = index.read_text().strip().splitlines()
    assert len(lines) == 5


def test_min_two_respected(tmp_path):
    p = make_project(tmp_path)
    seed_runs(p, count=2)
    agent_hook.cmd_gc(p, keep_per_agent=1)
    assert len(run_names(p / 'docs' / 'execution' / 'agent-runs')) == 2


def test_index_line_contains_session_and_note(tmp_path):
    p = make_project(tmp_path)
    seed_runs(p, count=25, note_fmt='第 {i} 次运行摘要')
    agent_hook.cmd_gc(p)
    first = (p / 'docs' / 'execution' / 'agent-runs' / 'archive' / 'index.md') \
        .read_text().strip().splitlines()[0]
    assert first.startswith('- ')
    assert '2026-11-08T10:00:00+08:00' in first
    assert 's-0' in first
    assert '第 0 次运行摘要' in first
    assert ' | ' in first


def test_interrupted_run_flagged_in_index(tmp_path):
    p = make_project(tmp_path)
    runs = seed_runs(p, count=21)
    # 让最旧的一个成为孤儿（旧心跳 + 未结束）
    oldest = runs / 'Codex-run00aaaaaaaaaaaaaaaaaa'
    rt = json.loads((oldest / 'runtime.json').read_text())
    rt['last_event'] = 'Interrupt'
    (oldest / 'runtime.json').write_text(json.dumps(rt))
    (oldest / '.lock').write_text('{"heartbeat": "2026-11-08T09:00:00+08:00", "pid": null}\n')
    agent_hook.cmd_gc(p)
    first = (p / 'docs' / 'execution' / 'agent-runs' / 'archive' / 'index.md') \
        .read_text().strip().splitlines()[0]
    assert first.startswith('- [中断]')


def test_handover_sections_compacted_with_pointer(tmp_path):
    p = make_project(tmp_path)
    handover = p / 'HANDOVER.md'
    handover.write_text('# 项目交接\n\n## 2026-11-08 会话 0\n- 内容 0\n\n'
                        + '\n'.join(f'## 2026-11-08 会话 {i}\n- 内容 {i}\n' for i in range(1, 7)))
    agent_hook.cmd_gc(p, handover_max_bytes=200, keep_sections=2)
    text = handover.read_text()
    assert '## 2026-11-08 会话 6' in text and '## 2026-11-08 会话 5' in text
    assert '## 2026-11-08 会话 1' not in text
    archive_dir = p / 'docs' / 'execution' / 'handoff-archive'
    archived = list(archive_dir.glob('*.md'))
    assert len(archived) == 1
    assert '## 2026-11-08 会话 1' in archived[0].read_text()
    assert 'handoff-archive' in text  # 指针留在 HANDOVER


def test_handover_without_sections_untouched(tmp_path):
    p = make_project(tmp_path)
    handover = p / 'HANDOVER.md'
    handover.write_text('# 交接\n只有一段没有小节结构的遗留内容\n')
    before = handover.read_bytes()
    agent_hook.cmd_gc(p, handover_max_bytes=10)
    assert handover.read_bytes() == before


def test_gc_idempotent(tmp_path):
    p = make_project(tmp_path)
    seed_runs(p, count=25)
    agent_hook.cmd_gc(p)
    snap = {str(f.relative_to(p)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(p.rglob('*')) if f.is_file()}
    agent_hook.cmd_gc(p)
    snap2 = {str(f.relative_to(p)): hashlib.sha256(f.read_bytes()).hexdigest()
             for f in sorted(p.rglob('*')) if f.is_file()}
    assert snap == snap2


def test_gc_command_smoke(tmp_path):
    p = make_project(tmp_path)
    r = run_cmd(p, '--gc', home=tmp_path / 'home')
    assert r.returncode == 0, r.stderr
    assert '归档' in r.stdout or '保留' in r.stdout
