# context-harness Design

## Summary

`context-harness` is an independent open-source project for turning local Code Agent conversations into a reusable personal context loop. It collects conversations from supported agents, stores them in a configurable data directory, extracts durable memory/profile signals, and exposes the resulting context back to Claude Code and Codex through files, hooks, skills, or plugin adapters.

V1 supports only two sources:

- Codex local sessions
- Claude Code local projects

Claude Web, Antigravity, ChatGPT, Gemini, and other sources are out of V1 scope. The architecture still leaves a collector boundary so they can be added later without rewriting the core.

## Goals

- Create a standalone project at `/Users/jialu/Documents/context-harness`.
- Let users fork the project and quickly collect local Code Agent conversations.
- Support custom conversation and memory storage locations.
- Keep the framework mechanism separate from user data.
- Support both direct CLI usage and Agent-driven usage through skills or plugin adapters.
- Provide one-command initialization for directories, global memory links, and automatic backup hooks.
- Make the data layer readable, editable, and portable as ordinary files.

## Non-Goals

- Do not store personal conversations, memory, or profile files inside the project repository.
- Do not build a daemon, database service, vector index, or hosted sync service in V1.
- Do not support browser-export workflows in V1.
- Do not make the memory extraction fully autonomous without user-visible review points.

## Core Model

`context-harness` separates the system into two layers.

The mechanism layer is the git repository:

```text
context-harness/
  context_harness/
  skills/
  plugins/
  templates/
  docs/
  tests/
```

The data layer is configurable through `CONTEXT_HARNESS_HOME` or a CLI flag:

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

Default data home:

```text
~/.context-harness
```

The project must never require user data to be committed into the mechanism repo. Templates may describe the layout, but real conversations and memory stay outside the repo unless a user intentionally configures otherwise.

## Architecture

### CLI

The CLI is the stable automation surface. Skills and plugins should call the CLI instead of duplicating implementation logic.

Expected V1 commands:

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

`init` creates or repairs the data directory, writes default config, creates memory/profile files when missing, and optionally installs hooks.

`sync` reads local source files, normalizes conversations to Markdown, and writes them to the configured data home.

`hooks install` idempotently installs automatic backup hooks for supported agents.

`dream` scans conversations and proposes memory/profile updates. It should produce a reviewable change summary before writing durable profile changes.

### Configuration

V1 configuration lives in `$CONTEXT_HARNESS_HOME/config.toml`.

Minimum shape:

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

Relative paths are resolved from `context_home`. Absolute paths are respected. This lets users store conversations, memory, and logs in separate locations if needed.

### Collectors

Collectors convert tool-specific local histories into a shared conversation archive format.

Collector interface:

```text
collect(source_config, mode) -> SyncResult
```

`mode` is either `latest N` or `all`.

Each collector is responsible for:

- locating local source records
- extracting user/assistant messages
- filtering tool noise and system/developer instructions
- deriving a stable conversation id
- writing normalized Markdown
- using state files and message counts for idempotent incremental sync

V1 collectors:

- `codex`: reads `~/.codex/sessions/` plus available session index metadata.
- `claude-code`: reads `~/.claude/projects/` JSONL files.

### Conversation Format

Conversation archives are Markdown files so they remain inspectable and agent-readable.

Required header fields:

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

The exact source may add optional fields such as project path, thread name, or local source file path. Tool calls and tool outputs are excluded by default.

### Hooks

Hooks are installation targets, not core business logic. Hook commands should be small and call the CLI:

```bash
context-harness sync codex --latest 1
context-harness sync claude-code --latest 1
```

Hook installers must be idempotent:

- create missing config files
- preserve unrelated user settings
- update old `context-harness` hook commands in place
- avoid blocking agent shutdown on sync failure
- write logs to a predictable log path

Codex hook target:

- project-local `.codex/config.toml`
- project-local `.codex/hooks.json`

Claude Code hook target:

- global `~/.claude/settings.json`

### Skills

Skills are the Agent-facing operating layer. They should stay concise and invoke the CLI for deterministic work.

V1 skills:

- `init-context`: initialize data directories, memory links, and hooks.
- `sync-conversations`: manually or automatically sync Codex and Claude Code conversations.
- `profile-dreamer`: scan archived conversations and propose memory/profile updates.

Skills should not contain private user data or hard-coded local paths from the original prototype.

### Plugin Adapters

Plugin adapters are optional wrappers for environments that support richer installation or tool exposure. They should map plugin actions to the same CLI commands used by skills.

The plugin layer should remain thin in V1:

- install or locate the CLI
- expose init/sync/dream actions
- report command output

## Initialization Flow

`context-harness init` performs these steps:

1. Resolve `context_home` from `--context-home`, `CONTEXT_HARNESS_HOME`, config, or default.
2. Create the data directory structure.
3. Write `config.toml` if missing.
4. Create initial memory/profile files if missing.
5. Create or update global context entry files for Claude Code and Codex.
6. Optionally install hooks for Codex and Claude Code.
7. Print a concise status report.

All steps must be safe to rerun.

## Memory Flow

`profile-dreamer` follows a review-first workflow:

1. Read `state/dream-state.json`.
2. Determine new or changed conversation files.
3. Extract durable profile signals from user statements, repeated preferences, decisions, and active projects.
4. Produce a change proposal grouped by add/update/strengthen/deprecate.
5. Wait for user confirmation before writing to `memory/user_profile.md` or `global-claude.md`.
6. Record the scan and accepted changes in `logs/dream.md`.
7. Update `state/dream-state.json`.

This preserves user agency and avoids silent profile drift.

## Error Handling

- Missing source directories should produce warnings, not hard failures.
- Malformed source records should be skipped with file-level diagnostics.
- Hook installation should back up files only when replacing non-symlink user-owned files.
- Sync commands should return non-zero for direct CLI failures, but hook commands should append `|| true` or equivalent so Agent shutdown is not blocked.
- State writes should be atomic where practical.

## Testing

V1 should include tests for:

- path resolution and config loading
- data directory initialization
- Codex collector parsing and noise filtering
- Claude Code collector parsing and incremental sync
- hook installer idempotency
- conversation Markdown rendering
- profile-dreamer scan boundary selection

Fixture data should be synthetic and small. Do not use real personal conversations in tests.

## Migration From Current Prototype

Reusable source material from the existing personal system:

- `sync-conversations` skill workflow
- Codex extractor and hook initializer
- Claude Code extractor
- `profile-dreamer` workflow
- `.context/scripts/init.sh` initialization concepts

Migration changes required:

- remove hard-coded `/Users/jialu/Documents/Engineer` paths
- replace direct script calls with CLI commands
- separate user data from mechanism files
- reduce V1 source scope to Codex and Claude Code
- move private profile assumptions into templates or examples

## V1 Decisions

- Package the CLI as a Python project managed by `uv`, because V1 collectors are file-processing heavy and the current prototype scripts are Python.
- Make hook installation opt-in with `context-harness init --install-hooks`, because hooks modify user Agent configuration files.
- Put `global-claude.md` at the data home root, because it acts as the compact context entry file rather than a detailed memory note.

These decisions can be revisited after V1 proves the local file loop.
