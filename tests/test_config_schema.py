"""Tolerant v1/v2 config schema (design §6.3, Task 3)."""
import importlib.util
import json

from conftest import SCRIPT, make_project, run_hook

spec = importlib.util.spec_from_file_location('agent_hook', SCRIPT)
agent_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_hook)

V1 = '{"version":1,"enabled":true}'
V2 = '{"version":2,"enabled":true}'


def test_v1_config_still_records(tmp_path):
    p = make_project(tmp_path, config=V1)
    r = run_hook(p, agent='Codex', event={'hook_event_name': 'SessionStart',
                                          'session_id': 's1', 'cwd': str(p)})
    assert (p / 'docs' / 'execution' / 'agent-runs').is_dir()
    assert r.returncode == 0


def test_v2_config_records(tmp_path):
    p = make_project(tmp_path, config=V2)
    r = run_hook(p, agent='Codex', event={'hook_event_name': 'SessionStart',
                                          'session_id': 's1', 'cwd': str(p)})
    assert (p / 'docs' / 'execution' / 'agent-runs').is_dir()
    assert r.returncode == 0


def test_extra_keys_tolerated(tmp_path):
    p = make_project(tmp_path, config='{"version":2,"enabled":true,"tasks":[],"custom":"x"}')
    settings, err = agent_hook.load_config(p / '.agent-handoff.json')
    assert err is None and settings['custom'] == 'x' and settings['tasks'] == []


def test_corrupt_json_skips_and_no_crash(tmp_path):
    p = make_project(tmp_path, config='not json')
    r = run_hook(p, agent='Codex', event={'hook_event_name': 'SessionStart',
                                          'session_id': 's1', 'cwd': str(p)})
    assert r.returncode == 0
    assert not (p / 'docs').exists()
    settings, err = agent_hook.load_config(p / '.agent-handoff.json')
    assert settings is None and 'JSON' in err


def test_unknown_version_rejected(tmp_path):
    p = make_project(tmp_path, config='{"version":3,"enabled":true}')
    settings, err = agent_hook.load_config(p / '.agent-handoff.json')
    assert settings is None and 'version' in err


def test_write_config_always_writes_v2(tmp_path):
    p = make_project(tmp_path, config=V1)
    agent_hook.write_config(p, {'enabled': False, 'custom': 'x'})
    data = json.loads((p / '.agent-handoff.json').read_text())
    assert data['version'] == 2 and data['enabled'] is False and data['custom'] == 'x'
