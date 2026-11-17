import hashlib
import json

import pytest

from conftest import make_project, run_hook


def ev(name, project, sid='kimi-session'):
    return {
        'hook_event_name': name,
        'session_id': sid,
        'session_title': 'Kimi compatibility',
        'client_type': 'kimi_code_cli',
        'cwd': str(project),
        'prompt': 'SECRET-KIMI-PROMPT',
    }


def run_dir(project, sid='kimi-session'):
    key = hashlib.sha256(sid.encode()).hexdigest()[:20]
    return project / 'docs' / 'execution' / 'agent-runs' / f'Kimi-{key}'


def test_kimi_session_start_records_run_without_context_output(tmp_path):
    project = make_project(tmp_path)
    result = run_hook(project, agent='Kimi', event=ev('SessionStart', project))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{}'
    runtime = json.loads((run_dir(project) / 'runtime.json').read_text())
    assert runtime['agent'] == 'Kimi'
    assert runtime['last_event'] == 'SessionStart'
    assert runtime['runtime_status'] == '会话已启动／恢复'


def test_kimi_prompt_injects_plain_context_and_keeps_prompt_private(tmp_path):
    project = make_project(tmp_path)
    result = run_hook(project, agent='Kimi', event=ev('UserPromptSubmit', project))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('本项目自动运行记录已建立：')
    assert 'hookSpecificOutput' not in result.stdout
    assert str(run_dir(project).relative_to(project)) in result.stdout
    for path in project.rglob('*'):
        if path.is_file():
            assert 'SECRET-KIMI-PROMPT' not in path.read_text(), path


def test_kimi_stop_uses_plain_nudge(tmp_path):
    project = make_project(tmp_path)
    result = run_hook(project, agent='Kimi', event=ev('Stop', project))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('运行状态已保存；交接记录尚有待填写项：')
    assert 'systemMessage' not in result.stdout
    runtime = json.loads((run_dir(project) / 'runtime.json').read_text())
    assert runtime['runtime_status'] == '回合结束，业务完成情况待核对'


@pytest.mark.parametrize('name,status', [
    ('Interrupt', '已中断，待接手'),
    ('SessionEnd', '会话已关闭，业务完成情况待核对'),
])
def test_kimi_terminal_events_record_status_without_context(tmp_path, name, status):
    project = make_project(tmp_path)
    result = run_hook(project, agent='Kimi', event=ev(name, project))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{}'
    runtime = json.loads((run_dir(project) / 'runtime.json').read_text())
    assert runtime['last_event'] == name
    assert runtime['runtime_status'] == status


@pytest.mark.parametrize('config', [None, '{"version":1,"enabled":false}'])
def test_kimi_missing_or_disabled_config_is_silent(tmp_path, config):
    project = make_project(tmp_path, config=config)
    result = run_hook(project, agent='Kimi', event=ev('SessionStart', project))

    assert result.returncode == 0, result.stderr
    assert not (project / 'docs').exists()
    assert result.stdout.strip() in ('', '{}')


def test_kimi_outside_project_cwd_is_ignored(tmp_path):
    project = make_project(tmp_path)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    result = run_hook(project, agent='Kimi', event=ev('SessionStart', elsewhere), cwd=elsewhere)

    assert result.returncode == 0, result.stderr
    assert not (project / 'docs').exists()
    assert not (elsewhere / 'docs').exists()
