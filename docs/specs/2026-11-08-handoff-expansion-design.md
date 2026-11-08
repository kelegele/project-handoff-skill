# Project Handoff 扩展设计：健壮性 / 功能 / Agent 支持

日期：2026-11-08。状态：待用户批准。
来源：与用户的头脑风暴会话（ZCode）。用户已确认的分叉用〔用户〕标注，本文作者（ZCode）的取舍用〔我的取舍〕标注，待验证项用〔待验证〕标注。

## 1. 意图与为什么

project-handoff 让「换一个 agent 接着干」不丢上下文：新会话先看交接状态再动手。维护者在多个客户端间接力工作，接入目标见 6.5 客户端矩阵。

刚公开的仓库（kelegele/project-handoff-skill，MIT）只有最小内核。本设计同时服务两个受众〔用户：both〕：

- **私人利器**：用户自己五客户端工作流的深度用法
- **公共工具**：陌生开发者一键可用

形态是**一个稳定公共内核 + 一层可丢弃的私人外壳**，边界是故意设计的：公共仓库只含通用源码；个人的交接配置、运行记录、定制全部留在本地（现有 .gitignore 模式已体现，要从「碰巧如此」变成「设计使然」）。

## 2. 现状（2026-11-08 已核验）

- 机制：用户级 STARTUP.md（经 ~/AGENTS.md 与各客户端入口指针链加载）→ 项目根 `.agent-handoff.json` 开关 → HANDOVER.md 交接 + 可选钩子自动记录到 `docs/execution/agent-runs/`
- 已发布：GitHub 公开仓库，本地远端一致（`5ed83a2`），MIT
- 钩子模板：Codex / ZCode / Qwen 三家有；Kimi 只有规则入口 + 文件交接
- 实证问题：真实 Codex 会话只有 SessionEnd 一条事件触发；项目脚本与模板手抄出现多处漂移；用户级安装文件可落后资产版；并发编辑 HANDOVER.md 可发生冲突
- 侦察结论：ChatGPT 桌面版与 Codex CLI 共享 `~/.codex/`（含 AGENTS.md 入口，已装指针）〔待验证：桌面版是否执行项目级 hooks.json〕；Pi 家目录 `~/.pi/agent/`（settings.json、mcp.json、skills、sessions、TypeScript 扩展系统）〔待验证：项目 AGENTS.md/steering 支持、扩展生命周期 API〕

## 3. 四条红线（用户反目标 → 不变量）

1. **未知 agent 不失效**：共享工件（`.agent-handoff.json`、HANDOVER.md）agent 中立；任何读 AGENTS.md 的客户端零配置获得 L0 文件交接；自动记录是加分项不是前提；新增客户端 = 矩阵加一行数据，不是抢救。
2. **配置即静默，被问必会答**：有效配置存在 → 绝不再问；损坏 → 报告具体问题而非装作首次；用户主动提起（开关/换客户端/排障/卸载）→ agent 走标准命令而非手抄，改完有验证输出。
3. **足迹自解释**：一条命令回答——这是什么、现在开还是关、哪些文件属于它、怎么关/怎么卸载。每个生成文件可追溯所有权，不依赖用户记忆。
4. **占用有界**：磁盘——运行记录自动轮转归档；上下文——HANDOVER.md 恒为「摘要+指针」，历史滚入 agent 默认不读的归档；GC 有硬预算。

## 4. 目标

三个轴：

- **健壮性**：doctor 自检、锁与孤儿回收、HANDOVER 并发安全、声明式安装、漂移检测、CI 回放测试、优雅降级阶梯
- **功能**：任务台账、SessionEnd 预填交接、agent 收件箱、决策日志、阻塞标记、git 关联、（可选）协作时间线
- **Agent 支持**：声明式客户端矩阵 + 客户端探测；把 ChatGPT（=Codex 别名）和 Pi 纳入；Claude Code、Copilot CLI、Cursor 等作为矩阵数据逐步补齐

## 5. 非目标

- 不做服务端、云依赖、跨机器同步（本地文件是唯一真相源）
- 不 fork 核心逻辑去适配某个客户端（客户端差异只允许存在于矩阵数据与薄适配层）
- 不依赖 Python 以外的运行时（钩子零三方依赖、3s 超时预算内完成、无网络调用）
- Windows 支持延后（钩子脚本保持 POSIX 路径习惯，不主动设障）
- 不修改各客户端原生行为；不承诺「钩子全覆盖才能用」——L0 永远可用

## 6. 架构

### 6.1 两层

- **公共内核**（仓库内）：启动提示词、模板、单一 CLI（见 6.3）、客户端矩阵、测试。美德是「少」。
- **私人层**（本地，永不入库）：`.agent-handoff.json`、HANDOVER.md、agent-runs、按客户端装的钩子配置、用户的定制模板。

### 6.2 降级阶梯

- **L0 文件交接**：AGENTS.md 兼容客户端读启动提示词 → 开关 + HANDOVER。任何 agent 可用。
- **L1 提示词配合**：agent 按 STARTUP.md 主动登记/更新交接（现在的主模式）。
- **L2 自动记录**：钩子写 events/runtime/handover 草稿。挂了不影响 L1/L0。

每层完整可用；升级只加便利不加依赖。

### 6.3 单一 CLI（现 agent_hook.py 演进，保持钩子调用入口不变）

`scripts/agent_hook.py` 兼容旧调用；新增子命令：

| 命令 | 作用 | 服务的红线 |
| --- | --- | --- |
| `--doctor` | 校验：配置有效、各客户端钩子注册、Python 版本、时区、写权限；输出体检报告 | 1、2 |
| `--enable` / `--disable` | 幂等开关，含钩子按需装卸；输出变更摘要与验证结果 | 2 |
| `--add-agent <name>` | 按矩阵数据接线一家客户端（复制模板、替换 `__COMMAND__`、合并不覆盖） | 1 |
| `--detect` | 扫描本机已装客户端的数据目录，报告可接线项 | 1 |
| `--status` | 自解释报告：模式、版本、入口链、本项目文件所有权清单、最近 3 次运行、占用统计、关闭/卸载方法 | 3 |
| `--gc` | 轮转归档（见 8.2、8.3），输出前后占用 | 4 |
| `--task new/update/close` | 任务台账（见 8.4） | 功能 |

全部幂等、可重入、3s 内完成（`--doctor`/`--gc` 可放宽）。手抄安装从此废除：agent 的配合动作 = 跑命令 + 核对输出。

**部署拓扑**〔我的取舍〕：CLI 只有一份**用户级中心副本**（`~/agent-project-handoff/` 下），各项目钩子命令一律指向它，靠 6.4 的 cwd 根解析定位项目——升级一处触达全部，漂移检测只看一份，项目内不再有脚本拷贝（现有 `scripts/agent_hook.py` 每项目拷贝模式正是漂移根源）。中心脚本缺失时钩子静默不记录（L0/L1 不受影响），`--doctor` 能查出。`--enable` 非交互默认：给 `--detect` 探测到且矩阵 status 非 research 的客户端全部接线。

### 6.4 项目根解析契约（红线 2 的地基，现在完全空白）

从会话 cwd 向上查找，先命中者即为根：

1. `.agent-handoff.json`（已启用项目，天然处理 monorepo 子目录）
2. `.git`
3. 到 `$HOME` 边界仍未命中 → 无项目上下文，静默跳过（不询问）

`$HOME` 本身不算项目。此规则写进 STARTUP.md 与钩子脚本，两边一致。

### 6.5 客户端矩阵（数据，不是代码）

`assets/clients.json`，每客户端一条：

```json
{
  "codex": {
    "entry_files": ["~/.codex/AGENTS.md"],
    "hook_config": {"path": ".codex/hooks.json", "format": "codex-hooks"},
    "events": {"session_start": "SessionStart", "prompt": "UserPromptSubmit", "stop": "Stop", "interrupt": "Interrupt", "session_end": "SessionEnd"},
    "status": "verified-partial"
  },
  "chatgpt": {"alias": "codex", "note": "共享 ~/.codex；桌面版项目钩子待验证"},
  "zcode": {"entry_files": ["~/.zcode/AGENTS.md"], "hook_config": {"path": ".zcode/config.json", "format": "zcode-hooks"}, "status": "template-only"},
  "kimi": {"entry_files": ["~/.kimi-code/AGENTS.md"], "hook_config": null, "status": "l0-only"},
  "pi": {"entry_files": ["~/.pi/agent/AGENTS.md(待定)"], "hook_config": null, "status": "research", "note": "v1 仅 L0/L1 入口接线，TS 扩展适配层留待后续版本"},
  "qwen": {"entry_files": ["~/.qwen/AGENTS.md"], "hook_config": {"path": ".qwen/settings.json", "format": "qwen-settings"}, "status": "template-only"},
  "generic-agentsmd": {"entry_files": ["./AGENTS.md"], "hook_config": null, "status": "l0"}
}
```

新增客户端 = 加一条数据 + 一次真实验收。`status` 字段诚实记录验证等级（verified / verified-partial / template-only / research / l0）。

## 7. 安装与分发

- 公共：`git clone` + 一条 `python3 scripts/agent_hook.py --install`（或 curl|sh 包一层）；`--dry-run` 先演算。〔我的取舍：v1 不上架各市场，仓库 + .skill 包双通道，市场后补〕
- 安装器职责：用户级目录、~/AGENTS.md 指针、各已探测客户端入口指针、按需钩子。幂等可重跑。
- 漂移检测与同步语义〔我的取舍〕：`--doctor` 对比用户级文件与资产版 hash。`--sync` 只更新「与资产版一致」的文件；**本地已修改（hash 不匹配）的一律保留并报告，绝不静默覆盖**，显式 `--force` 才覆盖。v1 存量装机不视为可丢弃：v1 的 `.agent-handoff.json` 在 v2 下继续有效（schema 只增字段）；旧钩子命令（绝对路径指向项目内脚本）继续可用，doctor 建议刷新为中心副本形态；存量项目的脚本漂移由用户决定保留或重装。

## 8. 记录生命周期与上下文预算

### 8.1 锁与孤儿回收（红线 1、4）

`.lock` 以**心跳时间戳为主**判定（每次事件刷新；钩子进程自身短命，其 PID 无判定价值，仅在负载提供客户端 PID 时附带记录）。新会话发现锁：心跳新鲜 → 并发会话，正常共处（各自 run 目录）；心跳超时（如 >30 分钟无事件）→ 该 run 标记 `interrupted`，归档，锁清除。

### 8.2 运行记录轮转（红线 4）

`--gc`（SessionStart 顺带跑）：每 agent 保留最近 20 个 run 目录（至少 2），更旧的删除目录、在 `archive/index.md` 追加单行摘要（时间、agent、session、git HEAD、一句话——由 handover.md 首行提取）。index 超 200 行裁最旧。磁盘占用逼近零增长。

### 8.3 HANDOVER.md 并发与体积（红线 2、4）

- 会话只**追加**自己的带日期小节，禁止改写他人小节；头部状态行只由本轮会话更新
- 超过 8KB / 300 行 → `--gc` 把旧小节移入 `docs/execution/handoff-archive/`，HANDOVER 保留头部 + 最近小节 + 指针
- agent 启动时只读 HANDOVER（小），不读归档（大）——上下文占用恒定

### 8.4 任务台账与交接增强

- `.agent-handoff.json` 增设 `tasks: [{id, owner, status, goal, next}]`（schema v2，向后兼容 v1——没有 tasks 字段即旧格式）〔我的取舍：结构存 JSON 而非 markdown，agent 读写无歧义；HANDOVER.md 渲染其摘要〕
- SessionEnd 钩子依据事件流预填 handover.md 草稿（回合数、时长、session_id、git HEAD），agent 补业务内容
- 收件箱 `docs/execution/inbox/<Agent>.md`：留言 append-only，新会话启动时 STARTUP.md 指示先读并签收
- 决策日志 `docs/execution/decisions.md`：append-only，用户确认的决定单列
- 阻塞标记：`.agent-handoff.json` 顶层 `blocked: "<原因>"` 或 `needs_user_input: "<问题>"`，启动检查第一眼汇报

## 9. 测试与验收

- pytest 回放矩阵进 CI（GitHub Actions，macOS + Linux）：缺配置询问 / 开 / 关 / 项目外忽略 / 子目录根解析 / 既有交接保留 / 输入正文不落盘 / 并发双会话 / 孤儿锁回收 / gc 轮转 / v1→v2 迁移
- 真实会话验收表（每客户端一次全新安装 + 真会话）：ZCode、Kimi、Codex、ChatGPT 桌面、Pi——结果回填矩阵 `status`。**验收异步补**〔我的取舍〕：真会话只能由用户在本机完成，不阻塞里程碑——代码与自动化测试先行，矩阵 status 诚实标注 verified / template-only / research，用户随时做了随时回填；M4 Release 不以「五家全部 verified」为闸门，status 诚实即可
- 〔待验证〕Pi：项目 AGENTS.md 与 steering 指令入口支持（v1 仅入口接线；扩展生命周期 API 留待后续版本调研）
- 〔待验证〕ChatGPT 桌面版是否执行项目 `.codex/hooks.json`
- 〔待验证〕Kimi Code CLI 是否有任何生命周期钩子入口

## 10. 里程碑

1. **M1 健壮性内核**：根解析契约、锁与回收、CLI（doctor/enable/disable/status/gc）、v2 schema、CI 回放矩阵
2. **M2 矩阵与五客户端验收**：clients.json、--detect/--add-agent、ChatGPT/Pi 入口验证回填（Pi 仅 L0/L1）、Kimi 调研定级
3. **M3 功能**：任务台账、SessionEnd 预填、收件箱、决策日志、阻塞标记、git 关联
4. **M4 发布**：安装器、文档、.skill 重打包、Release

（协作时间线等展示类功能不入 v1，留待有真实多会话数据后再议。〔我的取舍〕）

## 11. 已定与待定

**用户已定**：双受众（both）；四条红线；ChatGPT 桌面 agent 为本地执行；Pi 在 v1 仅做 L0/L1 入口接线（2026-11-08 补充）；本文档裁剪个人使用细节后提交入公共仓库（2026-11-08 补充）。

**我的取舍（可推翻）**：单 CLI 不拆多脚本；**CLI 为用户级中心副本、项目内不再拷贝脚本**；`--sync` 对已修改文件保留并报告、`--force` 才覆盖；孤儿判定以心跳为主；`--enable` 非交互默认接探测到的非 research 客户端；真会话验收异步补、Release 不设全验闸门；tasks 存 JSON；v2 向后兼容；归档只留 index；v1 不上架市场；展示类功能延后。

**待用户定**：（无——此前两项已于 2026-11-08 由用户裁定，见上。）

**待验证（实施期）**：见第 9 节三条〔待验证〕。
