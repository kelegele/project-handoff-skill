# Project Handoff Skill

A reusable workflow for handing off work across coding agents, one project at a time.

| Project state | New-session behavior |
| --- | --- |
| No `.agent-handoff.json` | Ask whether to enable, disable, or defer |
| `enabled: true` | Use project handoff and any configured local hooks |
| `enabled: false` | Continue without asking again |

## Repository layout

- `project-handoff/SKILL.md` is the Skill entry point.
- `project-handoff/assets/STARTUP.md` defines the new-session check.
- `project-handoff/assets/templates/` contains the files copied into individual projects.

Install the entire `project-handoff/` directory so the Skill can find its assets.

## Install

Place the `project-handoff` folder in your client's Skill directory, then ask it to set up the startup instructions using this Skill. The Skill appends references to existing instruction files. Startup behavior depends on the client loading and following those instructions.

Codex, ZCode and Kimi Code CLI have separate instruction entry points. Optional hook templates cover Codex, ZCode and the compatible Qwen Code engine. Kimi Code CLI uses file-based handoff in this release draft. Verify hook loading on the installed version before relying on automatic logging. Hooks require Python 3.9+ on macOS or Linux.

Session logs stay inside each project. The hook stores event metadata and creates a handoff note for the agent to complete. Keep generated run directories out of public repositories if the notes contain private task details.

## Release status

Local release draft. Suggested license: MIT, pending maintainer approval.
