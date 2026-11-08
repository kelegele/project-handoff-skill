"""Idempotent --enable / --disable commands (design §6.3, Task 5)."""
import hashlib
import json

from conftest import make_project, run_cmd, run_hook


def snapshot(project):
    return {str(f.relative_to(project)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(project.rglob('*')) if f.is_file()}


def test_enable_creates_three_artifacts(tmp_path):
    p = make_project(tmp_path, config=None)
    home = tmp_path / 'home'
    r = run_cmd(p, '--enable', home=home)
    assert r.returncode == 0, r.stderr
    cfg = json.loads((p / '.agent-handoff.json').read_text())
    assert cfg == {'version': 2, 'enabled': True}
    assert '## 多 Agent 交接' in (p / 'AGENTS.md').read_text()
    assert (p / 'HANDOVER.md').is_file()


def test_enable_idempotent(tmp_path):
    p = make_project(tmp_path, config=None)
    home = tmp_path / 'home'
    assert run_cmd(p, '--enable', home=home).returncode == 0
    before = snapshot(p)
    assert run_cmd(p, '--enable', home=home).returncode == 0
    assert snapshot(p) == before


def test_enable_preserves_existing_handover(tmp_path):
    p = make_project(tmp_path, config=None)
    (p / 'HANDOVER.md').write_text('# 我的自定义交接\n\n内容不许动\n')
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    assert (p / 'HANDOVER.md').read_text() == '# 我的自定义交接\n\n内容不许动\n'


def test_enable_aborts_on_corrupt_config(tmp_path):
    p = make_project(tmp_path, config='garbage text')
    r = run_cmd(p, '--enable', home=tmp_path / 'home')
    assert r.returncode == 2
    assert (p / '.agent-handoff.json').read_text() == 'garbage text'
    assert not (p / 'AGENTS.md').exists()
    assert not (p / 'HANDOVER.md').exists()


def test_disable_flips_flag_keeps_files(tmp_path):
    p = make_project(tmp_path)
    run_hook(p, event={'hook_event_name': 'SessionStart', 'session_id': 's1',
                       'cwd': str(p), 'prompt': 'SECRET-PROMPT'})
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    r = run_cmd(p, '--disable', home=tmp_path / 'home')
    assert r.returncode == 0, r.stderr
    cfg = json.loads((p / '.agent-handoff.json').read_text())
    assert cfg['enabled'] is False and cfg['version'] == 2
    assert '## 多 Agent 交接' in (p / 'AGENTS.md').read_text()
    assert (p / 'docs' / 'execution' / 'agent-runs').is_dir()


def test_disabled_project_stops_recording(tmp_path):
    p = make_project(tmp_path)
    run_cmd(p, '--disable', home=tmp_path / 'home')
    run_hook(p, event={'hook_event_name': 'SessionStart', 'session_id': 's1',
                       'cwd': str(p), 'prompt': 'SECRET-PROMPT'})
    assert not (p / 'docs' / 'execution' / 'agent-runs').is_dir()


def test_unresolvable_root_exit2(tmp_path):
    bare = tmp_path / 'bare'
    bare.mkdir()
    r = run_cmd(bare, '--enable', home=tmp_path / 'home')
    assert r.returncode == 2
    assert '未找到项目根' in r.stdout
