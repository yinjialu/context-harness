# context-harness 设计文档

## 概要

`context-harness` 是一个独立开源项目，用于把本地 Code Agent 对话转化为可复用的个人上下文闭环。它负责从受支持的 Agent 中收集 conversations，存入可配置的数据目录，提取长期有效的 memory/profile 信号，并通过 files、hooks、skills 或 plugin adapters 把沉淀后的上下文重新暴露给 Claude Code 和 Codex。

V1 只支持两个数据源：

- Codex local sessions
- Claude Code local projects

Claude Web、Antigravity、ChatGPT、Gemini 以及其他来源不在 V1 范围内。架构上仍然保留 collector 边界，后续可以在不重写 core 的情况下继续扩展。

## 目标

- 在 `/Users/jialu/Documents/context-harness` 创建独立项目。
- 让用户 fork 项目后，可以快速收集本地 Code Agent conversations。
- 支持自定义 conversations 和 memory 的存储位置。
- 保持 framework 机制和用户数据分离。
- 同时支持直接 CLI 使用，以及通过 skills 或 plugin adapters 由 Agent 驱动。
- 提供一键初始化能力，涵盖目录结构、全局 memory 入口和自动备份 hooks。
- 让数据层保持普通文件形态，方便阅读、编辑和迁移。

## 非目标

- 不把个人 conversations、memory 或 profile 文件存入项目仓库。
- V1 不构建 daemon、database service、vector index 或 hosted sync service。
- V1 不支持 browser-export 工作流。
- 不让 memory extraction 在缺少用户可见 review point 的情况下完全自动写入。

## 核心模型

`context-harness` 把系统拆成两层。

机制层是 git repository：

```text
context-harness/
  context_harness/
  skills/
  plugins/
  templates/
  docs/
  tests/
```

数据层通过 `CONTEXT_HARNESS_HOME` 或 CLI flag 配置：

```text
$CONTEXT_HARNESS_HOME/
  config.toml
  conversations/
    codex/
    claude-code/
  memory/
    MEMORY.md
    user_profile.md
  logs/
    dream.md
  state/
    sync-state.json
    dream-state.json
  exports/
```

默认 data home：

```text
~/.context-harness
```

项目不能要求用户把数据提交到机制层 repo。templates 可以描述目录布局，但真实 conversations 和 memory 默认留在 repo 之外，除非用户明确配置成其他行为。

## 架构

### CLI

CLI 是稳定的 automation surface。Skills 和 plugins 应该调用 CLI，而不是复制实现逻辑。

V1 预期命令：

```bash
context-harness init
context-harness init --context-home /path/to/context-home
context-harness sync codex --latest 1
context-harness sync codex --all
context-harness sync claude-code --latest 1
context-harness sync claude-code --all
context-harness hooks install codex
context-harness hooks install claude-code
context-harness dream --since last
```

`init` 创建或修复数据目录，写入默认 config，在缺失时创建 memory/profile 文件，并可选择安装 hooks。

`sync` 读取本地 source files，把 conversations 归一化为 Markdown，并写入配置的数据目录。

`hooks install` 以幂等方式为支持的 agents 安装自动备份 hooks。

`dream` 扫描 conversations 并提出 memory/profile 更新建议。在写入长期 profile 变更前，它必须产出可 review 的变更摘要。

### 配置

V1 configuration 位于 `$CONTEXT_HARNESS_HOME/config.toml`。

最小结构：

```toml
[paths]
context_home = "~/.context-harness"

[sources.codex]
enabled = true
sessions_dir = "~/.codex/sessions"
output_dir = "conversations/codex"

[sources.claude-code]
enabled = true
projects_dir = "~/.claude/projects"
output_dir = "conversations/claude-code"

[memory]
profile_file = "memory/user_profile.md"
global_context_file = "global-claude.md"
```

相对路径以 `context_home` 为基准解析；绝对路径保持原样。这样用户可以按需把 conversations、memory、logs 放在不同位置。

### Collectors

Collectors 负责把不同工具的本地历史记录转换成统一的 conversation archive 格式。

Collector interface：

```text
collect(source_config, mode) -> SyncResult
```

`mode` 可以是 `latest N` 或 `all`。

每个 collector 负责：

- 定位本地 source records
- 提取 user/assistant messages
- 过滤 tool noise 和 system/developer instructions
- 生成稳定的 conversation id
- 写入归一化 Markdown
- 使用 state files 和 message counts 实现幂等增量同步

V1 collectors：

- `codex`：读取 `~/.codex/sessions/`，并尽量结合可用的 session index metadata。
- `claude-code`：读取 `~/.claude/projects/` 下的 JSONL files。

### Conversation 格式

Conversation archives 使用 Markdown 文件，保持可检查、可编辑、Agent 可读。

必需 header 字段：

```markdown
# 2026-06-16 - Conversation title
- **Source**: codex
- **Session**: `<stable-session-id>`
- **Messages**: 12
- **Synced At**: 2026-06-16T12:34:56+08:00
---
### **User** 12:00
...
### **Assistant** 12:01
...
```

具体 source 可以添加可选字段，例如 project path、thread name 或 local source file path。Tool calls 和 tool outputs 默认排除。

### Hooks

Hooks 是安装目标，不承载核心业务逻辑。Hook commands 应该保持很小，只调用 CLI：

```bash
context-harness sync codex --latest 1
context-harness sync claude-code --latest 1
```

Hook installers 必须幂等：

- 创建缺失的 config files
- 保留无关的 user settings
- 原地更新旧的 `context-harness` hook commands
- 避免 sync failure 阻塞 agent shutdown
- 把日志写入可预测的 log path

Codex hook target：

- default user-level `~/.codex/config.toml`
- default user-level `~/.codex/hooks.json`
- optional project-local `.codex/config.toml` when `--scope project` is used
- optional project-local `.codex/hooks.json` when `--scope project` is used

Claude Code hook target：

- default user-level `~/.claude/settings.json`
- optional project-local `.claude/settings.json` when `--scope project` is used

### Skills

Skills 是面向 Agent 的操作层。它们应该保持简洁，并通过调用 CLI 完成确定性工作。

V1 skills：

- `init-context`：初始化 data directories、memory links 和 hooks。
- `sync-conversations`：手动或自动同步 Codex 与 Claude Code conversations。
- `profile-dreamer`：扫描 archived conversations，并提出 memory/profile 更新建议。

Skills 不应该包含 private user data，也不应该保留原型系统中的 hard-coded local paths。

### Plugin Adapters

Plugin adapters 是可选 wrapper，用于支持更丰富安装流程或 tool exposure 的环境。它们应该把 plugin actions 映射到 skills 使用的同一组 CLI commands。

V1 的 plugin layer 应该保持很薄：

- 安装或定位 CLI
- 暴露 init/sync/dream actions
- 回传 command output

## 初始化流程

`context-harness init` 执行以下步骤：

1. 从 `--context-home`、`CONTEXT_HARNESS_HOME`、config 或默认值解析 `context_home`。
2. 创建数据目录结构。
3. 在缺失时写入 `config.toml`。
4. 在缺失时创建初始 memory/profile files。
5. 创建或更新 Claude Code 和 Codex 可读的 global context entry files。
6. 可选安装 Codex 和 Claude Code hooks。
7. 打印简洁的 status report。

所有步骤都必须可安全重复执行。

## Memory 流程

`profile-dreamer` 采用 review-first workflow：

1. 读取 `state/dream-state.json`。
2. 判断新增或变化的 conversation files。
3. 从用户陈述、重复偏好、决策和活跃项目中提取长期有效的 profile signals。
4. 按 add/update/strengthen/deprecate 分组生成 change proposal。
5. 等待用户确认后，再写入 `memory/user_profile.md` 或 `global-claude.md`。
6. 在 `logs/dream.md` 记录扫描范围和已接受变更。
7. 更新 `state/dream-state.json`。

这能保留用户主体性，避免 profile 静默漂移。

## 错误处理

- 缺失 source directories 时给出 warnings，而不是直接 hard fail。
- 格式异常的 source records 应该跳过，并提供 file-level diagnostics。
- Hook installation 只有在替换非 symlink 的用户文件时才做备份。
- 直接运行 CLI 失败时，sync commands 应该返回 non-zero；但 hook commands 应该追加 `|| true` 或等价逻辑，避免阻塞 Agent shutdown。
- State writes 在可行时应保持 atomic。

## 测试

V1 应包含以下测试：

- path resolution 和 config loading
- data directory initialization
- Codex collector parsing 和 noise filtering
- Claude Code collector parsing 和 incremental sync
- hook installer idempotency
- conversation Markdown rendering
- profile-dreamer scan boundary selection

Fixture data 应该使用小规模合成数据。不要在 tests 中使用真实个人 conversations。

## 从当前原型迁移

当前个人系统中可复用的材料：

- `sync-conversations` skill workflow
- Codex extractor 和 hook initializer
- Claude Code extractor
- `profile-dreamer` workflow
- `.context/scripts/init.sh` 中的 initialization concepts

迁移时需要调整：

- 移除 hard-coded `/Users/jialu/Documents/Engineer` paths
- 用 CLI commands 替换直接脚本调用
- 分离 user data 和 mechanism files
- 把 V1 source scope 收敛到 Codex 和 Claude Code
- 把 private profile assumptions 移入 templates 或 examples

## V1 决策

- CLI 打包为由 `uv` 管理的 Python project，因为 V1 collectors 以文件处理为主，且当前原型脚本已经是 Python。
- Hook installation 通过 `context-harness init --install-hooks` 显式开启，因为 hooks 会修改用户的 Agent configuration files。
- `global-claude.md` 放在 data home root，因为它是 compact context entry file，而不是详细 memory note。

这些决策可以在 V1 跑通 local file loop 后再调整。
