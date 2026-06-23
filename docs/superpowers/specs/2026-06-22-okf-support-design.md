# context-harness OKF 支持 — 设计文档

日期：2026-06-22
状态：已确认，待实现

## 背景

[Open Knowledge Format (OKF)](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
是 Google Cloud 提出的开放知识表示规范，目标是让组织/个人的内部知识对 AI Agent 可移植、可互操作。

OKF v0.1 的核心约定：

- 知识库 = **一个 markdown 文件目录，每个文件带 YAML frontmatter**。
- frontmatter 唯一**强制字段是 `type`**；标准字段还有 `title`/`description`/`resource`/`tags`/`timestamp`，其余 producer 自定义。
- 概念之间用普通 markdown 相对链接互联，形成超越目录层级的关系图。
- 可选保留文件名：`index.md`（渐进式披露）、`log.md`（变更历史）。
- 设计原则：minimally opinionated、producer/consumer 解耦、format 而非 platform。

context-harness 的数据家目录（`context-harness-data/`，默认 `~/.context-harness`）本质上就是一个个人知识库：
归档对话（`conversations/<source>/*.md`）、memory（`memory/*.md`）、个人画像（`global-claude.md`）。
本设计让 context-harness **原生产出 OKF**，并提供存量迁移能力。

PR 落点：源码仓 `yinjialu/context-harness`（`/Users/jialu/Documents/context-harness`）。
存量数据迁移用新命令在本地数据家目录跑，数据仓改动单独 commit，不进代码 PR。

## 现状与差距

| 部分 | 现状 | OKF 差距 |
|---|---|---|
| 对话备份（`markdown.py::render_conversation`） | `# 标题` + bullet 元数据块，无 frontmatter | 缺 `type` 等 frontmatter |
| memory（`memory/*.md`） | 多数已有 `name`/`description`/`type`，但不统一（`insight_antigravity_backup.md` 用 `id`/`title`/`type: experience_document`） | 缺 `title`/`tags`/`timestamp`，type 取值需归一 |
| global-claude.md | 纯正文，无 frontmatter | 缺 frontmatter |
| 索引/历史 | memory 用 `MEMORY.md`，conversations 无索引 | 缺 OKF 风格 `index.md`/`log.md` |

## 设计

### 决策摘要

- **适配深度**：完整 OKF 重构（frontmatter + index.md + log.md + 互链）。
- **对话 `description`**：机器生成摘要（`<源> · <N> messages · project <X>`），不截取首条用户消息（避免敏感内容/不稳定）。
- **`MEMORY.md` 不改名**：保留为索引，加 `type: Index` frontmatter 使其成为合法 OKF 索引（理由见下）。

### 1. 对话备份 writer（最高优先级）

`context_harness/markdown.py::render_conversation` 在输出顶部加 OKF frontmatter，正文不变：

```yaml
---
type: Conversation
title: 帮我启动这个项目
description: claude-code · 30 messages · project AuraCare
source: claude-code
session: 5dc7bc0c-8d68-446d-951a-adc44668f028
messages: 30
created: 2026-05-10T09:56:12+08:00
tags: [conversation, claude-code]
timestamp: 2026-05-10T10:30:00+08:00
---
```

字段映射：

- `type`: 固定 `Conversation`（OKF 必填）。
- `title`: `conversation.title`。
- `description`: 机器生成 `<source> · <len(messages)> messages[ · project <name>]`。project 取自 `conversation.metadata` 中可推导的项目名（claude-code 来自 projects 路径），无则省略该段。
- `source` / `session` / `messages`: producer 字段。
- `created`: `conversation.created_at`（ISO8601 本地时区）。
- `timestamp`: `conversation.synced_at`（OKF 语义=最后更新）。
- `tags`: `[conversation, <source>]`。
- `conversation.metadata` 中的其余键继续作为 producer 字段输出。

### 2. OKF 索引/历史

新增模块 `context_harness/okf.py`：

- `render_frontmatter(fields: dict) -> str`：把有序字段渲染为 YAML frontmatter 块（list 用 flow 风格 `[a, b]`，字符串按需加引号，None/空跳过）。
- `build_dir_index(dir, entries, *, title, description) -> str`：生成 `index.md`（`type: Index`），列出条目链接、标题、关键元数据，做渐进式披露。
- `build_conversation_log(entries) -> str`：生成 `log.md`（`type: Log`），倒序时间线。
- 一个 `ConversationEntry` 轻量结构（路径、标题、created、messages 数）供索引/日志复用。

collector（`sync_claude_code` / `sync_codex`）在写完归档后，重建该 source 目录的 `index.md` 与 `log.md`；并重建 `conversations/index.md` 与家目录根 `index.md`。索引重建从目录现有文件 frontmatter 读取，保证幂等且与单条 sync 解耦。

互链：索引/日志中的条目用 OKF 约定的相对 markdown 链接（`[标题](20260510_5dc7bc0c.md)`）。

### 3. memory 适配

每个 memory 文件统一为 OKF frontmatter，**保留 `name`**（`[[链接]]` slug，全局记忆协议依赖）：

```yaml
---
type: project
name: harness-build-progress
title: Harness Build Progress
description: ...
tags: [project, harness]
timestamp: 2026-06-11T07:59:00+08:00
---
```

- `type` 归一到 `{user, project, feedback, reference, insight}`；`experience_document` → `insight`。
- 缺 `name` 的从文件名/旧 `id` 推导；缺 `title` 的从 `name`/旧 `title` 推导；缺 `timestamp` 的取文件 mtime。
- 原有非标字段（如 `originSessionId`）保留为 producer 字段。

**`MEMORY.md` 保留为索引，不改名**：Claude Code harness 内置 per-project 自动记忆协议（系统提示硬编码、不可改）写 `MEMORY.md`；OKF 的 `index.md` 是可选保留名而非强制。给 `MEMORY.md` 加 `type: Index` frontmatter 使其成为合法 OKF 索引，内容形态不变。

### 4. global-claude.md 适配

顶部加 frontmatter，正文不动：

```yaml
---
type: Personal Context
title: 关于我 — 尹家露
description: 个人画像、工作方式、当前关注与个人上下文系统入口
tags: [profile, personal-context]
timestamp: <mtime>
---
```

CLAUDE.md / AGENTS.md 容忍顶部 YAML 块（作为普通文本读入），不影响 `init.py` 已有的 `@import` / AGENTS.md 指针链接逻辑。

### 5. 迁移命令（存量适配）

新增 CLI 子命令 `context-harness migrate-okf [--dry-run]`：

- 原地为 `conversations/**/*.md`、`memory/*.md`、`global-claude.md` 补/修 frontmatter。
- 重建所有 `index.md` / `log.md`。
- **幂等**：已合规文件不产生 diff；可重复运行。
- `--dry-run` 只打印将变更的文件清单，不写盘。
- 解析已有 frontmatter 时保留未知 producer 字段，只补齐缺失标准字段，不破坏人工内容。

迁移逻辑复用 `okf.py` 与各类型的 frontmatter 构建函数，避免与 writer 重复实现。

### 6. 配套改动

- `init.py`：scaffold 根 `index.md`，模板（`MEMORY.md`/`user_profile.md`/`global-claude.md`）改为 OKF 形态（保留现有 global context 链接逻辑不动）。
- tests：`test_markdown.py`（对话 frontmatter）、新增 `test_okf.py`（frontmatter 渲染/索引/日志）、新增 `test_migrate_okf.py`（迁移幂等性、dry-run、各类型映射）、`test_init.py` 更新。
- 文档：`README.md` / `README.zh-CN.md` 增加 OKF 合规说明；`docs/agent-backup-adapter-architecture.md` 补 OKF 输出约定；`skills/sync-conversations`、`skills/init-context` 的 SKILL.md 同步。

## 单元边界

- `okf.py`：纯函数，输入数据结构 → 输出 markdown 字符串。无 IO，可独立测试。
- `markdown.py`：复用 `okf.render_frontmatter`，只负责单条对话渲染。
- collector：负责 IO 与索引重建编排，调用 `okf.py`。
- migrate（`okf.py` 内或独立模块）：负责存量解析/补齐，复用 `okf.py`。
- CLI：`migrate-okf` 子命令薄封装。

## 验证

- 全量 `pytest` 通过。
- `migrate-okf --dry-run` 在真实 `context-harness-data` 上输出预期文件清单。
- 实跑 `migrate-okf` 后：抽样校验 frontmatter 合法、`index.md`/`log.md` 链接可达、二次运行无 diff（幂等）。
- 触发一次 `sync claude-code`（hook 路径），确认新归档自带 OKF frontmatter 且索引被更新。

## 非目标

- 不修复 `~/.claude/CLAUDE.md` 的断软链（独立问题，另行处理）。
- 不改 OKF `resource` 字段语义（本地对话无对应 URL，省略）。
- 不引入 OKF 静态可视化/enrichment agent 等参考实现。
