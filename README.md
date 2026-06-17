# context-harness

`context-harness` 是一个 local-first 的个人 AI 上下文闭环框架。

V1 聚焦两个本地 Code Agent 数据源：

- Codex
- Claude Code

项目采用“机制层”和“用户数据层”分离的设计。仓库只维护 CLI、skills、hook installers、templates、docs 和 tests；conversations、memory、logs、sync state 等用户数据放在可配置的数据目录中，例如 `~/.context-harness`。

## 快速开始

以下命令默认在 `context-harness` 仓库根目录执行。

克隆仓库：

```bash
git clone https://github.com/yinjialu/context-harness.git
cd context-harness
```

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

为了让 repo-local skill 自动发现，仓库同时提供了两组相对 symlink：

```text
.agents/skills/      # Codex repo-local skills
.claude/skills/      # Claude Code repo-local skills
```

如果你想把这些 skills 安装为全局可用，可以在本机执行：

```bash
mkdir -p ~/.agents/skills ~/.claude/skills
ln -sfn /path/to/context-harness/skills/init-context ~/.agents/skills/init-context
ln -sfn /path/to/context-harness/skills/sync-conversations ~/.agents/skills/sync-conversations
ln -sfn /path/to/context-harness/skills/profile-dreamer ~/.agents/skills/profile-dreamer
ln -sfn /path/to/context-harness/skills/init-context ~/.claude/skills/init-context
ln -sfn /path/to/context-harness/skills/sync-conversations ~/.claude/skills/sync-conversations
ln -sfn /path/to/context-harness/skills/profile-dreamer ~/.claude/skills/profile-dreamer
```

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

hook 命令会读取 hook stdin 里的 `transcript_path`，优先同步当前结束的 transcript，而不是按全局 mtime 猜最近一条会话。安装时会记录 `context-harness` 仓库绝对路径；安装后如果移动或删除该仓库，需要重新安装 hooks。

Codex 的 command hook 可能需要额外 trust review。安装后如果 Codex 提示 hook 未信任，请在 Codex 里运行 `/hooks` 并确认 `context-harness` hook。

## 在 Codex 中使用

Codex 会从 repo 的 `.agents/skills/` 和用户级 `$HOME/.agents/skills` 发现 skills。打开 `context-harness` 仓库时，内置 skills 会通过 `.agents/skills` 自动暴露；如果你希望在任意项目里使用它们，请按上面的全局 symlink 方式安装到 `~/.agents/skills`。

常用方式：

```text
$init-context 初始化 context-harness，并按需安装 hooks
$sync-conversations 同步 Codex / Claude Code 对话记录
$profile-dreamer 从 conversations 中提取 memory / profile 候选更新
```

也可以用自然语言触发，例如：

```text
使用 sync-conversations 同步最近的 Codex 和 Claude Code 对话
使用 profile-dreamer 从最近归档中提取我的个人画像变化
```

推荐初始化流程：

```bash
uv run context-harness --context-home ~/.context-harness init
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
```

然后在 Codex 里运行 `/hooks`，确认 `context-harness` command hook 已被信任。之后 Codex Stop hook 会把 hook stdin 里的 `transcript_path` 传给 `context-harness`，优先归档当前结束的 transcript。

## 在 Claude Code 中使用

Claude Code 会发现 `.claude/skills/` 下的 project skills，也可以使用用户级 `~/.claude/skills`。打开 `context-harness` 仓库时，内置 skills 会通过 `.claude/skills` 自动暴露；如果你希望在任意项目里使用它们，请按上面的全局 symlink 方式安装到 `~/.claude/skills`。

常用方式：

```text
/init-context
/sync-conversations
/profile-dreamer
```

推荐初始化流程：

```bash
uv run context-harness --context-home ~/.context-harness init
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

Claude Code hook 默认写入 `~/.claude/settings.json`。Stop hook 会读取 hook stdin 中的 transcript 信息，并把当前会话归档到 `~/.context-harness/conversations/claude-code/`。

## 设计文档

- [docs/superpowers/specs/2026-06-16-context-harness-design.md](docs/superpowers/specs/2026-06-16-context-harness-design.md)
- [docs/superpowers/plans/2026-06-16-context-harness-v1-core.md](docs/superpowers/plans/2026-06-16-context-harness-v1-core.md)

## License

MIT
