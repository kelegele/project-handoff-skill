"""Heartbeat lock and orphan recovery (design §8.1, Task 4)."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

from conftest import SCRIPT, make_project, run_hook

spec = importlib.util.spec_from_file_location('agent_hook', SCRIPT)
agent_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_hook)

NOW = datetime(2026, 11, 8, 22, 0, 0)


def seed_run(runs_dir, run_id, last_event='UserPromptSubmit', heartbeat=None):
    run = runs_dir / run_id
    run.mkdir(parents=True)
    (run / 'runtime.json').write_text(json.dumps(
        {'run_id': run_id, 'agent': 'Codex', 'session_id': 's-' + run_id,
         'started_at': '2026-11-08T10:00:00+08:00', 'updated_at': '2026-11-08T10:30:00+08:00',
         'last_event': last_event, 'runtime_status': '进行中'}))
    (run / 'events.jsonl').write_text('')
    lock = run / '.lock'
    if heartbeat == 'empty':
        lock.write_text('')
    else:
        lock.write_text(agent_hook.heartbeat_payload(None, heartbeat) + '\n')
    return run


def test_heartbeat_payload_shape():
    line = json.loads(agent_hook.heartbeat_payload(4242, NOW))
    assert line == {'heartbeat': NOW.isoformat(timespec='seconds'), 'pid': 4242}
    assert json.loads(agent_hook.heartbeat_payload(None, NOW))['pid'] is None


def test_stale_lock_recovered(tmp_path):
    runs = tmp_path / 'agent-runs'
    run = seed_run(runs, 'Codex-old1', heartbeat=NOW - timedelta(minutes=31))
    recovered = agent_hook.recover_orphans(runs, NOW)
    assert recovered == ['Codex-old1']
    runtime = json.loads((run / 'runtime.json').read_text())
    assert runtime['interrupted'] is True
    assert runtime['runtime_status'] == '已中断（孤儿回收），待接手'
    assert not (run / '.lock').exists()


def test_empty_v1_lock_treated_as_stale(tmp_path):
    runs = tmp_path / 'agent-runs'
    seed_run(runs, 'Codex-old2', heartbeat='empty')
    assert agent_hook.recover_orphans(runs, NOW) == ['Codex-old2']


def test_fresh_concurrent_lock_untouched(tmp_path):
    runs = tmp_path / 'agent-runs'
    seed_run(runs, 'Codex-live', heartbeat=NOW - timedelta(minutes=5))
    assert agent_hook.recover_orphans(runs, NOW) == []
    assert (runs / 'Codex-live' / '.lock').is_file()
    runtime = json.loads((runs / 'Codex-live' / 'runtime.json').read_text())
    assert 'interrupted' not in runtime


def test_ended_run_untouched(tmp_path):
    runs = tmp_path / 'agent-runs'
    seed_run(runs, 'Codex-done', last_event='SessionEnd',
             heartbeat=NOW - timedelta(hours=2))
    assert agent_hook.recover_orphans(runs, NOW) == []
    runtime = json.loads((runs / 'Codex-done' / 'runtime.json').read_text())
    assert runtime['last_event'] == 'SessionEnd'


def test_concurrent_sessions_separate_runs(tmp_path):
    p = make_project(tmp_path)
    for sid in ('s1', 's2'):
        for name in ('SessionStart', 'UserPromptSubmit', 'Stop'):
            run_hook(p, event={'hook_event_name': name, 'session_id': sid,
                               'cwd': str(p), 'prompt': 'SECRET-PROMPT'})
    runs = sorted((p / 'docs' / 'execution' / 'agent-runs').iterdir())
    assert len(runs) == 2
    for run in runs:
        lines = (run / 'events.jsonl').read_text().strip().splitlines()
        assert len(lines) == 3
        assert [json.loads(l)['last_event'] for l in lines] == \
            ['SessionStart', 'UserPromptSubmit', 'Stop']
