# project-handoff

**换一个 agent 接着干，不用从头再讲一遍。**

[![GitHub stars](https://img.shields.io/github/stars/kelegele/project-handoff-skill?style=flat-square)](https://github.com/kelegele/project-handoff-skill/stargazers)
[![CI](https://img.shields.io/github/actions/workflow/status/kelegele/project-handoff-skill/tests.yml?branch=main&style=flat-square)](https://github.com/kelegele/project-handoff-skill/actions/workflows/tests.yml)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Agent Skill](https://img.shields.io/badge/格式-Agent_Skills-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9+-yellow?style=flat-square)

你上午用 Codex 开的会话，下午换 ZCode 接着干——新会话对项目一无所知：目标是什么、干到哪了、哪些决定不能翻、上次的坑在哪。你得从头讲一遍，或者眼睁睁看它把讲过的决定再违反一次。

project-handoff 把交接变成项目里的一组文件：新会话开工前先看交接状态再动手。谁接手都一样——它只依赖所有 agent 都认的 AGENTS.md 约定，不绑定任何一家客户端。

> 这个 skill 来自我自己的日常：五六个 agent 客户端来回切，每次交接都靠人肉复述。试过让 agent 自己写交接笔记，问题是没人管得住它的形状——有的越写越肥把上下文吃光，有的写完就忘没人接着看，还有的根本不知道该不该写。于是把交接本身固化成 skill：开关一次问清、记录自动落盘、体积有硬预算、怎么关怎么删全都说得明白。

## 30 秒开始

把仓库发给你的 agent：

> 帮我安装这个 skill：https://github.com/kelegele/project-handoff-skill ，装好后告诉我怎么用。

或者手动放进任意支持 Agent Skills 的客户端技能目录（目录名须为 `project-handoff`），然后对 AI 说：

> 用 project-handoff 给这个项目配置交接模式

装好后，每个新会话 AI 会自动做一件事：检查项目根目录的开关文件，问一次「要不要开启交接」，之后记住你的选择，绝不再问。

## 它能帮你做什么？

| 你手里的东西 | 它会怎么处理 |
|---|---|
| 一个多 agent 接力的项目 | 项目根一个开关文件 + 一份 HANDOVER.md 交接记录，谁来了先读谁接着写 |
| 「换了个 agent 就不认识交接文件」的担忧 | 共享工件只依赖 AGENTS.md 通用约定；不认识的客户端零配置获得文件交接，自动记录只是加分项 |
| 「配好了还反复问我开不开」的烦躁 | 有效配置存在即静默沿用；配置损坏时点名具体问题，绝不装作首次询问 |
| 「这堆文件是干嘛的、怎么关」的遗忘 | `--status` 一条命令答全：这是什么、开还是关、哪些文件属于它、怎么关怎么删 |
| 运行日志和交接记录越攒越肥 | `--gc` 自动轮转：运行记录每 agent 留 20 条压成归档索引，交接记录超预算只留最近小节，其余进归档 |
| 半路死掉的会话没人收尾 | 心跳锁自动判孤儿：超时会话标记「已中断，待接手」，下一个 agent 一眼看到 |
| 交接配置被改坏了 | `--doctor` 逐项体检（配置/钩子/权限/时区），PASS/FAIL/WARN 分级报告，坏在哪说得具体 |

## 四条设计红线

1. **未知 agent 不失效**——任何会读 AGENTS.md 的客户端，零配置获得完整文件交接；自动记录挂了不影响交接本身。
2. **配置即静默，被问必会答**——配好不再问；你主动提开关/排障/卸载时，agent 走标准命令，不手抄不瞎改。
3. **足迹自解释**——一条 `--status` 回答：是什么、什么状态、哪些文件是它的、怎么卸载。
4. **占用有界**——磁盘与上下文占用都有硬预算，运行多久都不会拖垮项目。

## 服务命令（对 AI 说「帮我体检交接配置」即可）

| 命令 | 作用 |
|---|---|
| `agent_hook.py --enable` | 为本项目开启交接（幂等，坏配置中止不碰文件） |
| `agent_hook.py --disable` | 关闭（只翻开关，保留全部记录） |
| `agent_hook.py --doctor` | 体检：配置 / 钩子接线 / 权限 / 时区 |
| `agent_hook.py --status` | 自解释报告：模式、入口链、文件所有权、最近运行、占用、卸载方法 |
| `agent_hook.py --gc` | 轮转运行记录 + 交接记录瘦身 |

## 安装

### Agent Skills 客户端

把仓库放进技能目录，目录名须为 `project-handoff`：

| Agent | 全局技能目录 |
|---|---|
| 跨 agent 通用 | `~/.agents/skills/` |
| ZCode | `~/.zcode/skills/` |
| Codex | `~/.codex/skills/` |

装好后对 AI 说「用 project-handoff 给这个项目配置交接模式」，它会完成用户级安装（启动提示词、AGENTS.md 指针）并逐项目询问开关。

### 下载安装包

到 [Releases](https://github.com/kelegele/project-handoff-skill/releases) 下载 `project-handoff.skill`，解压得到 `project-handoff/` 目录，按上表放进技能目录。

### 客户端入口指针（可选自动记录）

| 客户端 | 用户级指令入口 | 自动记录 |
|---|---|---|
| Codex | `~/.codex/AGENTS.md` | ✅ 钩子已在真实会话实证 |
| ZCode | `~/.zcode/AGENTS.md` | 模板就绪，真实会话验收中 |
| Kimi Code CLI | `~/.kimi-code/AGENTS.md` | 暂无钩子，文件交接完整可用 |
| 其他 AGENTS.md 兼容客户端 | 项目根 `AGENTS.md` | 文件交接完整可用 |

> 钩子自动记录需要 macOS 或 Linux、Python 3.9+。各客户端钩子成熟度不同，`--doctor` 会如实报告你本机每家的接线状态；接不上的客户端不影响文件交接。

## 隐私

钩子只记录事件元数据（事件名、时间、会话编号），**从不记录**提示词、回复、命令内容或对话记录——有测试专门钉住这条承诺。运行记录留在每个项目自己的 `docs/execution/` 里，不外发。

## 仓库结构

```
project-handoff-skill/
├── project-handoff/             # 可安装 Skill 本体
│   ├── SKILL.md                 # 安装与项目行为说明
│   ├── LICENSE
│   └── assets/
│       ├── STARTUP.md           # 新会话启动检查（含服务手册）
│       └── templates/           # 开关 / 交接 / 钩子模板 + 核心脚本
├── docs/specs/                  # 设计文档
├── tests/                       # 回放测试矩阵（45 个用例）
└── .github/workflows/           # CI：macOS + Linux × Python 3.10 / 3.13
```

## 更新

git clone 安装的拉取最新；手动复制 / Release 下载的重新覆盖一遍：

```bash
git -C ~/.agents/skills/project-handoff pull
```

> 更新后部分 agent 需重启或新开对话才能加载新版。

## FAQ

**会反复问我开不开吗？**
不会。首次询问一次，之后有效配置直接沿用；配置坏了会点名问题，不会装作没配置过。

**换一个它不认识的 agent 还能用吗？**
能。共享工件只依赖 AGENTS.md 通用约定，任何兼容客户端读同一份文件交接；新客户端的自动记录支持是加一行配置数据的事。

**文件会越攒越多拖垮项目吗？**
不会。运行记录每 agent 保留 20 条，更旧的压成归档索引单行；交接记录超 8KB / 300 行自动瘦身，只留最近 3 节，其余进归档——agent 平时只读小文件。

**它记录我的对话内容吗？**
不记录。钩子白名单只含事件名、时间与会话编号，有测试专门验证提示词正文不落盘。

**怎么彻底卸载？**
`--status` 会给出路径：删掉项目里的 `.agent-handoff.json` 与 `docs/execution/`，去掉 AGENTS.md 交接段，再把技能目录里的 `project-handoff/` 删掉即可，全程无残留依赖。

**项目外的目录会被误处理吗？**
不会。主目录、临时目录不算项目；根解析只认 `.agent-handoff.json` 或 `.git`，越界即静默跳过。

## 反馈

遇到问题或有想法，欢迎 [提 issue](https://github.com/kelegele/project-handoff-skill/issues)。

## License

[MIT](LICENSE)
