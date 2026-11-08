"""Project root resolution contract (design §6.4)."""
import importlib.util
import json
import os
import subprocess

from conftest import SCRIPT, make_project, run_hook

spec = importlib.util.spec_from_file_location('agent_hook', SCRIPT)
agent_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_hook)

resolve = agent_hook.resolve_project_root


def test_subdir_finds_root_by_config(tmp_path):
    p = make_project(tmp_path)
    deep = p / 'src' / 'deep'
    deep.mkdir(parents=True)
    assert resolve(deep, tmp_path / 'home') == p


def test_git_only_root(tmp_path):
    p = make_project(tmp_path, config=None)
    (p / 'src').mkdir()
    assert resolve(p / 'src', tmp_path / 'home') == p


def test_monorepo_package_config_wins_over_parent_git(tmp_path):
    p = make_project(tmp_path, config=None)
    pkg = p / 'packages' / 'a'
    pkg.mkdir(parents=True)
    (pkg / '.agent-handoff.json').write_text('{"version":1,"enabled":true}')
    assert resolve(pkg / 'src', tmp_path / 'home') == pkg


def test_home_itself_never_a_project(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.git').mkdir()
    (home / '.agent-handoff.json').write_text('{"version":1,"enabled":true}')
    (home / 'work').mkdir()
    assert resolve(home, home) is None
    assert resolve(home / 'work', home) is None


def test_no_marker_returns_none(tmp_path):
    a = tmp_path / 'a'
    a.mkdir()
    assert resolve(a, tmp_path / 'home') is None


def test_central_copy_script_records_by_event_cwd(tmp_path):
    """The contract T2 introduces: script may live outside the project."""
    p = make_project(tmp_path)
    env = dict(os.environ, HOME=str(tmp_path / 'home'))
    event = json.dumps({'hook_event_name': 'SessionStart', 'session_id': 's1',
                        'cwd': str(p), 'prompt': 'SECRET-PROMPT'})
    r = subprocess.run(['python3', str(SCRIPT), '--agent', 'Codex'],
                       input=event, capture_output=True, text=True, env=env)
    assert r.returncode == 0
    runs = p / 'docs' / 'execution' / 'agent-runs'
    assert any(runs.iterdir()), 'central copy must record via cwd resolution'


def test_event_from_subdir_records_into_project(tmp_path):
    p = make_project(tmp_path)
    sub = p / 'src'
    sub.mkdir()
    run_hook(p, event={'hook_event_name': 'SessionStart', 'session_id': 's1',
                       'cwd': str(sub), 'prompt': 'SECRET-PROMPT'})
    runs = p / 'docs' / 'execution' / 'agent-runs'
    assert any(runs.iterdir())
