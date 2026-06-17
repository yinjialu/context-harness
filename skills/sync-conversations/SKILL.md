---
name: sync-conversations
description: Sync local Codex and Claude Code conversation records into a context-harness data home. Use when the user asks to back up Code Agent conversations, sync Codex sessions, sync Claude Code sessions, run full or incremental conversation backup, or inspect context-harness sync status.
license: MIT
---

# Sync Conversations

Use this skill to collect local Code Agent conversations into `context-harness`. The skill can bootstrap the CLI runtime even when only the skill was installed.

## Runtime Bootstrap

Before running `context-harness`, execute the bundled bootstrap script from this skill directory:

```bash
runtime_dir="$(bash scripts/bootstrap.sh)"
cd "$runtime_dir"
```

The script clones or updates the runtime repository at `~/.local/share/context-harness` by default, checks out `v0.1.1`, and runs `uv sync`.

Overrides:

- `CONTEXT_HARNESS_RUNTIME_DIR`: custom runtime checkout path.
- `CONTEXT_HARNESS_REPO_URL`: custom fork URL.
- `CONTEXT_HARNESS_REF`: custom branch, tag, or commit.
- `CONTEXT_HARNESS_BOOTSTRAP_SKIP_UPDATE=1`: skip fetch/pull.

## Sources

V1 supports:

- `codex`
- `claude-code`

Claude Web, Antigravity, ChatGPT, Gemini, and browser exports are outside V1.

## Workflow

1. Run the Runtime Bootstrap steps above. Use the returned path as the `context-harness` repository root.
2. Resolve the context home from `CONTEXT_HARNESS_HOME`, the user's explicit path, or `~/.context-harness`.
3. Change to the runtime repository root.
4. Run the requested sync command from the repository root.
5. Summarize `checked`, `created`, `updated`, `skipped`, and `output_dir`.

## Commands

Before running any command, first run the Runtime Bootstrap steps and change to the returned repository root. Run all `uv run context-harness ...` commands from that root.

Incremental sync:

```bash
uv run context-harness --context-home <context-home> sync codex --latest 1
uv run context-harness --context-home <context-home> sync claude-code --latest 1
```

Full sync:

```bash
uv run context-harness --context-home <context-home> sync codex --all
uv run context-harness --context-home <context-home> sync claude-code --all
```

After running, summarize `checked`, `created`, `updated`, `skipped`, and `output_dir`.
