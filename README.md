# project-handoff

**Hand off work across coding agents — without re-explaining everything.**

[English](README.md) | [简体中文](README.zh-CN.md)

[![GitHub stars](https://img.shields.io/github/stars/kelegele/project-handoff-skill?style=flat-square)](https://github.com/kelegele/project-handoff-skill/stargazers)
[![CI](https://img.shields.io/github/actions/workflow/status/kelegele/project-handoff-skill/tests.yml?branch=main&style=flat-square)](https://github.com/kelegele/project-handoff-skill/actions/workflows/tests.yml)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Agent Skill](https://img.shields.io/badge/格式-Agent_Skills-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9+-yellow?style=flat-square)

A session you ran in Codex this morning gets picked up in ZCode this afternoon — and the new session knows nothing: what the goal is, where things stand, which decisions are off-limits, which pitfall cost you an hour last week. You re-explain everything, or watch it redo the very approach you already rejected.

project-handoff turns handoff into a set of files inside the project: every new session reads the handoff state before touching anything. Any agent, same treatment — it relies only on the AGENTS.md convention that all major clients already honor, and is bound to no single vendor.

> This skill came out of my own daily grind: six agent clients, every switch a manual re-briefing. I tried letting agents write their own handoff notes — nothing kept their shape in check. Some grew until they ate the context window, some got written and never read, some never got written at all. So I turned handoff itself into a skill: ask about the switch once, log runs automatically, enforce hard size budgets, and always answer how to turn it off or remove it.

## Start in 30 seconds

```bash
npx skills add kelegele/project-handoff-skill
```

Then say to your agent:

> Set up project handoff for this project using project-handoff

Rather have the agent do the installing? Just send it the repo:

> Install this skill for me: https://github.com/kelegele/project-handoff-skill , then tell me how to use it.

Or drop it into any Agent Skills directory yourself (folder name must be `project-handoff`) and say:

> Use project-handoff to set up handoff mode for this project

Once installed, every new session does one thing automatically: check the switch file at the project root, ask once whether to enable handoff, then remember your choice — never asks again.

## When do you need this?

- **You switch between AI coding clients** — Codex in the morning, ZCode in the afternoon, Kimi at night; you don't want to re-brief on every switch
- **Projects span days or weeks with sessions opening and closing** — you want to pick up where things left off, not reconstruct progress from chat history
- **You're forced to switch tools mid-stream** — quota exhausted, context window full, a model temporarily unavailable; the new tool must instantly know what's done and what's untouchable
- **You've been burned by a half-told story** — forgot to mention approach A was rejected, and the agent cheerfully rebuilt it; forgot the dependency had a pitfall, and it stepped in the same one
- **Multiple people (or agents) rotate on one project** — when you log off, whoever picks it up needs the same "here's where we are"

## When NOT to use it

- **You use a single agent client and never switch** — the handoff files are pure overhead: one client's own session memory is enough; this mechanism exists for crossing tools and sessions
- **You don't know what an agent is, and don't manage AI tools yourself** — this skill assumes you open multiple agent sessions, understand the AGENTS.md convention, and can have an agent run commands and check their output; if you only use web chat AIs, or someone else manages your tooling, extra files and prompts will just get in the way
- **Throwaway scripts and one-off repos** — there is no "next session"; handoff has nothing to hand off
- **Projects that allow no extra files at all** — handoff lives in in-project files (the switch, records, archives are all inspectable and removable; `--status` lists them); if your environment audits repo cleanliness hard, evaluate first

## What does it do for you?

| What you have | What it does |
|---|---|
| A multi-agent relay project | One switch file + one HANDOVER.md at the project root; whoever arrives reads it, whoever leaves updates it |
| Fear that "a new agent won't recognize the handoff files" | Shared artifacts depend only on the AGENTS.md convention; unknown clients get full file-based handoff with zero setup — auto-logging is a bonus, never a prerequisite |
| Annoyance of being asked "enable or not" over and over | A valid config means silence; a corrupt config gets a specific problem report, never a fake first-time prompt |
| Forgetting what these files are or how to turn it off | `--status` answers in one command: what this is, on or off, which files belong to it, how to disable or uninstall |
| Run logs and handoff notes growing without bound | `--gc` rotates automatically: keeps the 20 newest runs per agent as one-line archive entries, compacts the handover file past budget, archives the rest |
| Sessions that died mid-way with nobody wrapping up | Heartbeat locks detect orphans: timed-out sessions get flagged "interrupted, pick up here" for the next agent |
| A handoff config someone broke | `--doctor` checks every item (config / hook wiring / permissions / timezone) with PASS/FAIL/WARN and names exactly what's wrong |

## Four design promises

1. **Unknown agents don't break it** — any client that reads AGENTS.md gets full file-based handoff with zero setup; if auto-logging fails, handoff itself still works.
2. **Configured means silent; asked means answered** — never re-ask once configured; when you raise switching / diagnostics / uninstall, the agent runs the standard commands instead of improvising edits.
3. **Self-explaining footprint** — one `--status` answers: what it is, what state it's in, which files are its, how to uninstall.
4. **Bounded footprint** — disk and context usage have hard budgets; the project never drowns in its own logs.

## Service commands (say "run a handoff checkup" to your agent)

| Command | Purpose |
|---|---|
| `agent_hook.py --enable` | Enable handoff for this project (idempotent; aborts without touching files on a corrupt config) |
| `agent_hook.py --disable` | Disable (flips the flag only; keeps every record) |
| `agent_hook.py --doctor` | Checkup: config / hook wiring / permissions / timezone |
| `agent_hook.py --status` | Self-explaining report: mode, entry chain, file ownership, recent runs, usage, uninstall steps |
| `agent_hook.py --gc` | Rotate run records + compact the handover file |

## Install

### npx skills (recommended)

```bash
npx skills add kelegele/project-handoff-skill
```

### Manual copy into a skills directory

Folder name must be `project-handoff`:

| Agent | Global skills directory |
|---|---|
| Cross-agent universal | `~/.agents/skills/` |
| ZCode | `~/.zcode/skills/` |
| Codex | `~/.codex/skills/` |

Then say "use project-handoff to set up handoff mode for this project" — it completes the user-level install (startup instructions, AGENTS.md pointer) and asks per project.

### Download the package

Grab `project-handoff.skill` from [Releases](https://github.com/kelegele/project-handoff-skill/releases), unzip to get the `project-handoff/` directory, and place it per the table above.

### Client entry pointers (optional auto-logging)

| Client | User-level instruction entry | Auto-logging |
|---|---|---|
| Codex | `~/.codex/AGENTS.md` | ✅ Hook verified in real sessions |
| ZCode | `~/.zcode/AGENTS.md` | Template ready; real-session acceptance in progress |
| Kimi Code CLI | `~/.kimi-code/AGENTS.md` | No hooks yet; file-based handoff fully works |
| Other AGENTS.md-compatible clients | project-root `AGENTS.md` | File-based handoff fully works |

> Auto-logging hooks need macOS or Linux with Python 3.9+. Hook maturity varies per client; `--doctor` reports your machine's actual wiring honestly. Clients without hooks still get full file-based handoff.

## Privacy

Hooks log event metadata only (event name, timestamp, session id) and **never** log prompts, responses, commands, or transcripts — a test exists specifically to pin this promise. Run records stay inside each project's `docs/execution/` and are never sent anywhere.

## Repository layout

```
project-handoff-skill/
├── project-handoff/             # The installable skill
│   ├── SKILL.md                 # Install & project behavior
│   ├── LICENSE
│   └── assets/
│       ├── STARTUP.md           # New-session check (with service manual)
│       └── templates/           # Switch / handover / hook templates + core script
├── docs/specs/                  # Design documents
├── tests/                       # Replay test matrix (45 cases)
└── .github/workflows/           # CI: macOS + Linux × Python 3.10 / 3.13
```

## Update

Match your install method (see [CHANGELOG](CHANGELOG.md) for what changed):

**npx skills install**: use the CLI's update command

```bash
npx skills update project-handoff   # just this one; omit the name to update all
```

**git clone install**: pull inside the cloned directory

```bash
git -C ~/.agents/skills/project-handoff pull
```

**Manual copy / Release download**: overwrite the `project-handoff/` directory in your skills directory.

> Some agents need a restart or a fresh conversation to load the new version.

## FAQ

**Will it keep asking me enable-or-disable?**
No. It asks once, then honors the saved choice. If the config is corrupt it names the problem instead of pretending nothing was configured.

**Does it work with an agent it has never heard of?**
Yes. Shared artifacts depend only on the AGENTS.md convention; any compatible client reads the same file-based handoff. Adding auto-logging for a new client is one line of config data.

**Will the files pile up and drown the project?**
No. Run records keep the newest 20 per agent, older ones compress to one-line archive entries; the handover file compacts past 8KB / 300 lines, keeping the 3 most recent sections — agents normally read only small files.

**Does it record my conversations?**
No. The hook whitelist contains event names, timestamps, and session ids only; tests specifically verify prompt text never lands on disk.

**How do I remove it completely?**
`--status` prints the path: delete `.agent-handoff.json` and `docs/execution/` in the project, remove the handoff section from AGENTS.md, and delete `project-handoff/` from the skills directory. No hidden dependencies anywhere.

**Will it misfire outside a project?**
No. Home and temp directories are never treated as projects; root resolution only recognizes `.agent-handoff.json` or `.git`, and bails out silently past the boundary.

## Feedback

Issues and ideas are welcome at [GitHub Issues](https://github.com/kelegele/project-handoff-skill/issues).

## Related

- [agentsmd-skill](https://github.com/kelegele/agentsmd-skill) — solidify session lessons into AGENTS.md rules. agentsmd remembers *how* to work; project-handoff remembers *where you left off*.
- Blog: [usage guide](https://www.kelegele.com/blog/project-handoff-scene-guide) · [agentsmd scene guide](https://www.kelegele.com/blog/agentsmd-scene-guide) · [agentsmd design philosophy](https://www.kelegele.com/blog/agents-md-lessons-without-bloat)

## Author

**[kelegele](https://github.com/kelegele)** · [kelegele.com](https://kelegele.com) · more agent tooling on [GitHub](https://github.com/kelegele?tab=repositories)

## License

[MIT](LICENSE)
