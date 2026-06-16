# context-harness

`context-harness` 是一个 local-first 的个人 AI 上下文闭环框架。

V1 聚焦两个本地 Code Agent 数据源：

- Codex
- Claude Code

项目采用“机制层”和“用户数据层”分离的设计。仓库只维护 CLI、skills、hook installers、templates、docs 和 tests；conversations、memory、logs、sync state 等用户数据放在可配置的数据目录中，例如 `~/.context-harness`。

## 快速开始

以下命令默认在 `context-harness` 仓库根目录执行。

安装依赖：

```bash
uv sync
```

初始化数据目录：

```bash
uv run context-harness --context-home ~/.context-harness init
```

同步最近一条 Codex conversation：

```bash
uv run context-harness --context-home ~/.context-harness sync codex --latest 1
```

同步最近一条 Claude Code conversation：

```bash
uv run context-harness --context-home ~/.context-harness sync claude-code --latest 1
```

安装自动同步 hooks：

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

## 自定义数据目录

`context-harness` 支持两种方式指定数据目录：

```bash
CONTEXT_HARNESS_HOME=~/Documents/my-context uv run context-harness init
uv run context-harness --context-home ~/Documents/my-context init
```

`--context-home` 优先级高于 `CONTEXT_HARNESS_HOME`。初始化后可以修改数据目录里的 `config.toml`，自定义 Codex / Claude Code 的原始对话记录位置和归档输出位置。

示例：

```toml
[sources.codex]
enabled = true
sessions_dir = "~/Library/Application Support/Codex/sessions"
output_dir = "conversations/codex"

[sources.claude-code]
enabled = true
projects_dir = "~/Documents/claude-code-projects"
output_dir = "conversations/claude-code"

[memory]
profile_file = "memory/user_profile.md"
global_context_file = "global-claude.md"
```

相对路径会按 `context_home` 解析，绝对路径和 `~` 会保持对应语义。

## 数据目录结构

初始化后，用户数据目录大致如下：

```text
~/.context-harness/
  config.toml
  global-claude.md
  conversations/
    codex/
    claude-code/
  memory/
    MEMORY.md
    user_profile.md
  state/
    codex-sync-state.json
    claude-code-sync-state.json
```

其中：

- `conversations/` 保存从 Code Agent 原始记录渲染出来的 Markdown 归档。
- `memory/` 保存 profile-dreamer 等工作流维护的记忆文件。
- `state/` 保存增量同步状态，用于避免重复处理未变化的 session。
- `config.toml` 只描述本机路径和开关，不需要提交到机制仓库。

## Skills

仓库内置三个 Agent-facing skills：

- `skills/init-context`：初始化数据目录，并按需安装 Codex / Claude Code hooks。
- `skills/sync-conversations`：手动触发全量或增量 conversation 同步。
- `skills/profile-dreamer`：从归档 conversation 中提取个人画像和 memory 候选更新。

这些 skills 只负责描述 Agent 工作流，实际能力由 CLI 提供，避免把业务逻辑散落到多个 Agent prompt 里。

## Hooks

V1 的 hooks 目标是让 Codex 和 Claude Code 在合适时机自动调用同步命令，把新 conversation 归档到 `context_home`。

Codex hook 写入目标项目的 `.codex/config.toml` 和 `.codex/hooks.json`。在目标项目根目录执行时，可以省略 `--project-root`：

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex
```

如果从 `context-harness` 仓库根目录给其他项目安装，请显式传入目标项目路径：

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
```

Claude Code hook 默认写入 `~/.claude/settings.json`：

```bash
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

hook installer 是幂等的，重复执行会更新已有的 context-harness sync hook，不会清空已有的其他 hook 配置。

hook 命令会记录安装时的 `context-harness` 仓库绝对路径；安装后如果移动或删除该仓库，需要重新安装 hooks。

## 设计文档

- [docs/superpowers/specs/2026-06-16-context-harness-design.md](docs/superpowers/specs/2026-06-16-context-harness-design.md)
- [docs/superpowers/plans/2026-06-16-context-harness-v1-core.md](docs/superpowers/plans/2026-06-16-context-harness-v1-core.md)
