"""Self-explaining --status and --doctor (design §6.3, Task 7)."""
from conftest import make_project, run_cmd


def wire_codex(p):
    hooks = p / '.codex' / 'hooks.json'
    hooks.parent.mkdir(exist_ok=True)
    hooks.write_text('{"hooks": {"SessionStart": [{"hooks": [{"command": '
                     '"python3 scripts/agent_hook.py --agent Codex"}]}]}}')


def test_status_shows_all_sections_and_disable_hint(tmp_path):
    p = make_project(tmp_path)
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    wire_codex(p)
    r = run_cmd(p, '--status', home=tmp_path / 'home')
    assert r.returncode == 0, r.stderr
    for section in ('模式', '入口链', '文件所有权', '最近运行', '占用', '如何关闭'):
        assert section in r.stdout
    assert '--disable' in r.stdout
    assert 'Codex' in r.stdout and '指向本系统脚本' in r.stdout


def test_doctor_healthy_exit0(tmp_path):
    p = make_project(tmp_path)
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    wire_codex(p)
    r = run_cmd(p, '--doctor', home=tmp_path / 'home')
    assert r.returncode == 0, r.stderr
    assert '[PASS]' in r.stdout
    assert '[FAIL]' not in r.stdout


def test_doctor_corrupt_config_exit1_names_problem(tmp_path):
    p = make_project(tmp_path, config='broken {{{')
    r = run_cmd(p, '--doctor', home=tmp_path / 'home')
    assert r.returncode == 1
    assert 'JSON' in r.stdout


def test_doctor_unwritable_execution_fail(tmp_path):
    p = make_project(tmp_path)
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    exec_dir = p / 'docs' / 'execution'
    exec_dir.parent.mkdir(exist_ok=True)
    exec_dir.write_text('blocked')  # 同名普通文件挡住目录
    r = run_cmd(p, '--doctor', home=tmp_path / 'home')
    assert r.returncode == 1
    assert '[FAIL] docs/execution 可写' in r.stdout


def test_doctor_unwired_hooks_warn_not_fail(tmp_path):
    p = make_project(tmp_path)
    assert run_cmd(p, '--enable', home=tmp_path / 'home').returncode == 0
    r = run_cmd(p, '--doctor', home=tmp_path / 'home')
    assert r.returncode == 0
    assert '[WARN]' in r.stdout and '未接线' in r.stdout
