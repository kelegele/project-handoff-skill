import hashlib
import json

import pytest

from conftest import make_project, run_hook


AGENTS = ['Codex', 'ZCode', 'QwenWork', 'Pi']
STATUSES = {
    'SessionStart': '会话已启动／恢复',
    'UserPromptSubmit': '进行中',
    'Stop': '回合结束，业务完成情况待核对',
    'Interrupt': '已中断，待接手',
    'SessionEnd': '会话已关闭，业务完成情况待核对',
}


@pytest.mark.parametrize('agent', AGENTS)
@pytest.mark.parametrize('name', list(STATUSES))
def test_existing_agent_event_contract_is_unchanged(tmp_path, agent, name):
    project = make_project(tmp_path)
    sid = f'{agent}-session'
    event = {
        'hook_event_name': name,
        'session_id': sid,
        'cwd': str(project),
        'prompt': 'SECRET-LEGACY-PROMPT',
    }
    result = run_hook(project, agent=agent, event=event)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    if name in {'SessionStart', 'UserPromptSubmit'}:
        assert payload['hookSpecificOutput']['hookEventName'] == name
        assert 'additionalContext' in payload['hookSpecificOutput']
    elif name == 'Stop':
        assert '运行状态已保存' in payload['systemMessage']
    else:
        assert payload == {}

    key = hashlib.sha256(sid.encode()).hexdigest()[:20]
    run_id = f'{agent}-{key}'
    run = project / 'docs' / 'execution' / 'agent-runs' / run_id
    runtime = json.loads((run / 'runtime.json').read_text())
    assert runtime['run_id'] == run_id
    assert runtime['agent'] == agent
    assert runtime['last_event'] == name
    assert runtime['runtime_status'] == STATUSES[name]
    handover = (run / 'handover.md').read_text()
    assert f'运行编号：{run_id}' in handover
    assert f'负责 Agent：{agent}' in handover
    for path in project.rglob('*'):
        if path.is_file():
            assert 'SECRET-LEGACY-PROMPT' not in path.read_text(), path
