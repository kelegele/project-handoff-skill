"""Shared sandbox fixtures: build throwaway projects and replay real hook calls.

The v1 script resolves the project root from its own location (scripts/ copy
inside the project), so run_hook() deploys a fresh copy into each sandbox
project before invoking it — the same deployment model production v1 uses.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'project-handoff' / 'assets' / 'templates' / 'scripts' / 'agent_hook.py'

V1_CONFIG = '{"version":1,"enabled":true}'


def make_project(tmp_path, config=V1_CONFIG, git=True, home=None):
    """Create a sandbox project; returns its root. config=None omits the switch."""
    project = tmp_path / 'proj'
    project.mkdir()
    if git:
        (project / '.git').mkdir()
    if config is not None:
        (project / '.agent-handoff.json').write_text(config)
    if home is not None:
        Path(home).mkdir(parents=True, exist_ok=True)
    return project


def run_hook(project, agent='Codex', event=None, cwd=None, home=None, raw_stdin=None):
    """Deploy SCRIPT into project/scripts/ (v1 model) and run it as a subprocess."""
    deployed = project / 'scripts' / 'agent_hook.py'
    deployed.parent.mkdir(exist_ok=True)
    shutil.copyfile(SCRIPT, deployed)
    if raw_stdin is not None:
        payload = raw_stdin
    else:
        payload = json.dumps(event or {
            'hook_event_name': 'SessionStart', 'session_id': 's1',
            'cwd': str(project), 'prompt': 'SECRET-PROMPT',
        })
    env = dict(os.environ)
    if home is not None:
        env['HOME'] = str(home)
    return subprocess.run(
        ['python3', str(deployed), '--agent', agent],
        input=payload, capture_output=True, text=True,
        cwd=str(cwd or project), env=env,
    )
