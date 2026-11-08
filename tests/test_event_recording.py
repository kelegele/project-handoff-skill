"""Pin v1 hook behavior before any refactor (characterization tests)."""
import hashlib
import json

from conftest import make_project, run_hook

STATUSES = {
    'SessionStart': '会话已启动／恢复',
    'UserPromptSubmit': '进行中',
    'Stop': '回合结束，业务完成情况待核对',
    'Interrupt': '已中断，待接手',
    'SessionEnd': '会话已关闭，业务完成情况待核对',
}


def ev(name, sid='s1', cwd=None):
    return {
        'hook_event_name': name, 'session_id': sid,
        'cwd': str(cwd), 'prompt': 'SECRET-PROMPT',
    }


def run_dir(project, agent='Codex', sid='s1'):
    key = hashlib.sha256(sid.encode()).hexdigest()[:20]
    return project / 'docs' / 'execution' / 'agent-runs' / f'{agent}-{key}'


def test_session_start_creates_run_and_context(tmp_path):
    p = make_project(tmp_path)
    r = run_hook(p, event=ev('SessionStart', 's1', p))
    run = run_dir(p)
    assert (run / 'runtime.json').is_file()
    assert (run / 'events.jsonl').is_file()
    assert (run / 'handover.md').is_file()
    assert json.loads(r.stdout)['hookSpecificOutput']['hookEventName'] == 'SessionStart'


def test_prompt_text_never_landed(tmp_path):
    p = make_project(tmp_path)
    run_hook(p, event=ev('UserPromptSubmit', 's1', p))
    for f in p.rglob('*'):
        if f.is_file():
            assert 'SECRET-PROMPT' not in f.read_text(), f'leaked into {f}'


def test_outside_project_cwd_ignored(tmp_path):
    p = make_project(tmp_path)
    other = tmp_path / 'elsewhere'
    other.mkdir()
    r = run_hook(p, event=ev('SessionStart', 's1', other))
    assert not (p / 'docs').exists()
    assert r.stdout.strip() in ('', '{}')


def test_malformed_stdin_no_crash(tmp_path):
    p = make_project(tmp_path)
    r = run_hook(p, raw_stdin='not-json')
    assert r.returncode == 0
    assert not (p / 'docs').exists()


def test_missing_config_no_record(tmp_path):
    p = make_project(tmp_path, config=None)
    r = run_hook(p, event=ev('SessionStart', 's1', p))
    assert r.returncode == 0
    assert not (p / 'docs').exists()


def test_event_status_mapping(tmp_path):
    p = make_project(tmp_path)
    for name, status in STATUSES.items():
        r = run_hook(p, event=ev(name, 's1', p))
        assert r.returncode == 0
        runtime = json.loads((run_dir(p) / 'runtime.json').read_text())
        assert runtime['last_event'] == name
        assert runtime['runtime_status'] == status
    lines = (run_dir(p) / 'events.jsonl').read_text().strip().splitlines()
    assert len(lines) == 5
    assert all(json.loads(l)['last_event'] in STATUSES for l in lines)
    # Stop with an unfilled handover surfaces a systemMessage nudge.
    stop = run_hook(p, event=ev('Stop', 's2', p))
    assert 'systemMessage' in json.loads(stop.stdout)
