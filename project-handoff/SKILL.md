---
name: project-handoff
description: Install or manage opt-in project handoff for coding agents. Use when the user wants a new-session handoff prompt, shared AGENTS.md instructions, per-project on/off choices, cross-agent handover, or optional local run logs.
license: MIT
homepage: https://kelegele.com
repository: https://github.com/kelegele/project-handoff-skill
author: kelegele (https://github.com/kelegele)
---

# Project handoff

Install the startup instructions when the user asks to set up this workflow. For a project session where the startup instructions are already installed, follow [STARTUP.md](assets/STARTUP.md). Installing the Skill alone does not register a startup action.

## Install the startup instructions

1. Resolve the user's actual home directory and confirm which clients they use. Inspect their existing instruction files and links. Preserve every existing rule.
2. Copy the contents of `assets/` to a stable user-owned directory such as `~/agent-project-handoff/`. Reuse identical files. If destination contents differ, inspect and merge or present the conflict before overwriting.
3. Append a short pointer to the installed `STARTUP.md` to the user's shared `~/AGENTS.md` if an equivalent pointer is absent. Resolve the path to an absolute path for this machine.
4. In each selected client's supported user instruction entry, append a reference asking the agent to read the shared `AGENTS.md` before starting project work. Reuse an existing equivalent reference. Check the installed client and its documentation when its data directory is customized or its entry point is uncertain.

| Client | Default entry |
| --- | --- |
| Codex | `~/.codex/AGENTS.md` |
| ZCode | `~/.zcode/AGENTS.md` |
| Kimi Code CLI | `~/.kimi-code/AGENTS.md` |
| Pi | `~/.pi/AGENTS.md` |

5. Read back the pointer chain. Verify on a new session when possible. Distinguish file installation, instruction loading, and actual hook execution in your report.

## Project behavior

The project root's `.agent-handoff.json` is the shared choice. Ask once per session if the file is missing. On enable, merge handoff rules and install only compatible optional hooks. On disable, save the false setting. On defer, leave the choice unset. Honor existing valid choices and report invalid settings. Switch an existing choice only at the user's request.

Use the templates in `assets/templates/`. Pi has no hooks config: wire it with the project-local extension template `.pi/extensions/project-handoff.ts` (set `HOOK_SCRIPT` to the shared `agent_hook.py` absolute path; it forwards lifecycle events with `--agent Pi`). Never overwrite existing handoff notes or unrelated hook entries. If a client has no verified lifecycle hook entry point, use file-based handoff. Keep runtime records separate from task completion evidence.
