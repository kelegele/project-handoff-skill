import importlib.util
import os
import stat
import subprocess

import pytest

from conftest import SCRIPT, make_project


BEGIN = '# >>> project-handoff:kimi-hooks:v1 >>>'
END = '# <<< project-handoff:kimi-hooks:v1 <<<'
EVENTS = ['SessionStart', 'UserPromptSubmit', 'Stop', 'Interrupt', 'SessionEnd']


def run_kimi(project, kimi_home, *flags, home=None):
    env = dict(os.environ)
    env['HOME'] = str(home or project.parent / 'home')
    env['KIMI_CODE_HOME'] = str(kimi_home)
    Path = type(project)
    Path(env['HOME']).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ['python3', str(SCRIPT), *flags],
        capture_output=True, text=True, cwd=project, env=env,
    )


def test_enable_creates_five_hooks_and_status_is_read_only(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'

    enabled = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')

    assert enabled.returncode == 0, enabled.stderr
    config = kimi_home / 'config.toml'
    text = config.read_text()
    assert text.count(BEGIN) == 1
    assert text.count(END) == 1
    assert [text.index(f'event = "{name}"') for name in EVENTS] == sorted(
        text.index(f'event = "{name}"') for name in EVENTS
    )
    assert text.count('[[hooks]]') == 5
    assert text.count('timeout = 5') == 5
    assert str(SCRIPT) in text
    assert '--agent Kimi' in text
    assert not (project.parent / 'home' / '.kimi-code').exists()

    before = config.read_bytes()
    status = run_kimi(project, kimi_home, '--kimi-hooks', 'status')
    assert status.returncode == 0, status.stderr
    assert '已接线' in status.stdout
    assert str(config) in status.stdout
    assert config.read_bytes() == before


def test_enable_preserves_unrelated_bytes_and_is_idempotent(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = (
        'default_model = "PRIVATE-MODEL"\r\n'
        '[[hooks]]\r\n'
        'event = "Notification"\r\n'
        'command = "PRIVATE-COMMAND"'
    )
    config.write_bytes(original.encode())

    first = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')
    assert first.returncode == 0, first.stderr
    once = config.read_bytes()
    assert once.startswith(original.encode())
    assert 'PRIVATE-MODEL' not in first.stdout + first.stderr
    assert 'PRIVATE-COMMAND' not in first.stdout + first.stderr

    second = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')
    assert second.returncode == 0, second.stderr
    assert config.read_bytes() == once


def test_disable_removes_only_the_managed_block(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    prefix = 'default_model = "PRIVATE-MODEL"\n'
    suffix = '[[hooks]]\nevent = "Notification"\ncommand = "PRIVATE-COMMAND"\n'
    config.write_text(prefix + suffix)

    assert run_kimi(project, kimi_home, '--kimi-hooks', 'enable').returncode == 0
    enabled_text = config.read_text()
    enabled_text = enabled_text.replace(suffix, '', 1) + suffix
    config.write_text(enabled_text)

    disabled = run_kimi(project, kimi_home, '--kimi-hooks', 'disable')
    assert disabled.returncode == 0, disabled.stderr
    assert config.read_text() == prefix + suffix
    assert 'PRIVATE-MODEL' not in disabled.stdout + disabled.stderr
    assert 'PRIVATE-COMMAND' not in disabled.stdout + disabled.stderr


@pytest.mark.parametrize('marker', [BEGIN, END])
@pytest.mark.parametrize('action', ['enable', 'disable'])
def test_partial_marker_conflict_aborts_without_writing(tmp_path, marker, action):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = f'# PRIVATE-SETTINGS\n{marker}\ncommand = "PRIVATE-COMMAND"\n'
    config.write_text(original)

    result = run_kimi(project, kimi_home, '--kimi-hooks', action)

    assert result.returncode != 0
    assert '冲突' in result.stdout
    assert config.read_text() == original
    assert 'PRIVATE-SETTINGS' not in result.stdout + result.stderr
    assert 'PRIVATE-COMMAND' not in result.stdout + result.stderr


def test_unmanaged_kimi_command_conflicts_without_writing(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = (
        '[[hooks]]\n'
        'event = "SessionStart"\n'
        'command = "python3 /private/agent_hook.py --agent Kimi"\n'
    )
    config.write_text(original)

    result = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')

    assert result.returncode != 0
    assert '未受管' in result.stdout
    assert config.read_text() == original
    assert '/private/agent_hook.py' not in result.stdout + result.stderr


def test_missing_wiring_warns_without_failing_file_handoff(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    assert run_kimi(project, kimi_home, '--enable').returncode == 0

    status = run_kimi(project, kimi_home, '--status')
    doctor = run_kimi(project, kimi_home, '--doctor')

    assert status.returncode == 0, status.stderr
    assert 'Kimi Code CLI' in status.stdout
    assert '未接线' in status.stdout
    assert doctor.returncode == 0, doctor.stderr
    assert '[WARN] 入口链: Kimi Code CLI' in doctor.stdout
    assert '文件交接仍可用' in doctor.stdout



def test_complete_but_invalid_managed_block_is_repaired(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    config.write_text(f'{BEGIN}\n# incomplete managed block\n{END}\n')
    assert run_kimi(project, kimi_home, '--enable').returncode == 0

    status = run_kimi(project, kimi_home, '--kimi-hooks', 'status')
    doctor = run_kimi(project, kimi_home, '--doctor')
    assert '内容异常' in status.stdout
    assert '[WARN] 入口链: Kimi Code CLI' in doctor.stdout

    repaired = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')
    assert repaired.returncode == 0, repaired.stderr
    text = config.read_text()
    assert text.count('[[hooks]]') == 5
    for name in EVENTS:
        assert f'event = "{name}"' in text
    assert '已接线' in run_kimi(project, kimi_home, '--kimi-hooks', 'status').stdout


def test_complete_but_invalid_managed_block_can_be_disabled(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    prefix = 'default_model = "PRIVATE-MODEL"\n'
    config.write_text(f'{prefix}{BEGIN}\n{END}\n')

    disabled = run_kimi(project, kimi_home, '--kimi-hooks', 'disable')

    assert disabled.returncode == 0, disabled.stderr
    assert config.read_text() == prefix


def test_old_managed_script_path_is_updated(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    config = kimi_home / 'config.toml'
    assert run_kimi(project, kimi_home, '--kimi-hooks', 'enable').returncode == 0
    config.write_text(config.read_text().replace(str(SCRIPT), '/old/agent_hook.py'))

    assert '已接线' in run_kimi(project, kimi_home, '--kimi-hooks', 'status').stdout
    updated = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')
    assert updated.returncode == 0, updated.stderr
    assert '/old/agent_hook.py' not in config.read_text()
    assert str(SCRIPT) in config.read_text()


@pytest.mark.parametrize('argument', ['--agent=Kimi', "--agent 'Kimi'", '--agent "Kimi"'])
def test_unmanaged_kimi_argument_variants_conflict(tmp_path, argument):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = (
        '[[hooks]]\n'
        'event = "SessionStart"\n'
        f'command = "python3 /private/agent_hook.py {argument}"\n'
    )
    config.write_text(original)

    result = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')

    assert result.returncode != 0
    assert '未受管' in result.stdout
    assert config.read_text() == original


def test_kimi_words_outside_hook_commands_do_not_conflict(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = (
        '# command = "python3 agent_hook.py --agent Kimi"\n'
        'default_model = "agent_hook.py --agent Kimi"\n'
    )
    config.write_text(original)

    result = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')

    assert result.returncode == 0, result.stderr
    assert config.read_text().startswith(original)


def test_write_uses_unique_temp_files_and_preserves_private_mode(tmp_path):
    project = make_project(tmp_path)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    config.write_text('default_model = "PRIVATE-MODEL"\n')
    config.chmod(0o600)
    victim = tmp_path / 'victim'
    victim.write_text('DO-NOT-CHANGE')
    stale_tmp = kimi_home / '.config.toml.project-handoff.tmp'
    stale_tmp.symlink_to(victim)

    result = run_kimi(project, kimi_home, '--kimi-hooks', 'enable')

    assert result.returncode == 0, result.stderr
    assert victim.read_text() == 'DO-NOT-CHANGE'
    assert stale_tmp.is_symlink()
    assert not config.is_symlink()
    assert stat.S_IMODE(config.stat().st_mode) == 0o600


def test_replace_failure_is_nonzero_and_preserves_original(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('agent_hook_review_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    kimi_home = tmp_path / 'kimi-home'
    kimi_home.mkdir()
    config = kimi_home / 'config.toml'
    original = b'default_model = "PRIVATE-MODEL"\n'
    config.write_bytes(original)
    monkeypatch.setenv('KIMI_CODE_HOME', str(kimi_home))

    def fail_replace(source, destination):
        raise OSError('simulated replace failure')

    monkeypatch.setattr(module.os, 'replace', fail_replace)
    result = module.cmd_kimi_hooks('enable')

    assert result != 0
    assert config.read_bytes() == original
    output = capsys.readouterr()
    assert '写入失败' in output.out
    assert 'PRIVATE-MODEL' not in output.out + output.err
