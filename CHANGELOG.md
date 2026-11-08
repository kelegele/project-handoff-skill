# Changelog

版本号：vMAJOR.MINOR.PATCH。MINOR 功能新增、PATCH 修订、MAJOR 架构级变更。

## v0.1.0 - 2026-11-08

首个公开发布。

### Added

- 可安装 Skill：新会话启动检查（一次询问、沿用选择）、用户级安装流程、项目开关 `.agent-handoff.json`、HANDOVER.md 交接模板与 AGENTS.md 规则段
- 可选钩子模板：Codex / ZCode / Qwen Code 三客户端；Codex 钩子已在真实会话实证（SessionEnd 事件）
- cwd 根解析契约：向上查找 `.agent-handoff.json`（优先）与 `.git`，$HOME 与文件系统根永不算项目；monorepo 子目录正确归属
- 配置 schema v1/v2 宽容读写：v1 永远有效；损坏配置「不记录、不崩溃、doctor 点名」
- 心跳锁与孤儿回收：超时（>30 分钟）且未正常关闭的运行标记「已中断，待接手」并清锁
- 幂等命令：`--enable` / `--disable` / `--gc` / `--status` / `--doctor`——坏配置中止不碰文件，disable 零删除
- 运行记录轮转：每 agent 保留最近 20 个 run，更旧压入归档索引单行（含中断标记、git HEAD、一句话摘要）
- HANDOVER 瘦身：超 8KB / 300 行时只保留最近 3 个会话小节，其余移入归档并留指针；无小节结构的遗留内容一字不动
- STARTUP 服务手册：用户请求 → 命令 → 验证对照表，agent 变更一律走命令不手抄
- 隐私承诺：钩子白名单只记事件元数据，提示词正文不落盘（测试钉住）
- 回放测试矩阵 45 例 + GitHub Actions CI（macOS / Linux × Python 3.10 / 3.13）
