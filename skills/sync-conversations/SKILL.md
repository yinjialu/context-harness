---
name: sync-conversations
description: Sync local Codex and Claude Code conversation records into a context-harness data home. Use when the user asks to back up Code Agent conversations, sync Codex sessions, sync Claude Code sessions, run full or incremental conversation backup, or inspect context-harness sync status.
---

# Sync Conversations

Use this skill to collect local Code Agent conversations into `context-harness`.

## Sources

V1 supports:

- `codex`
- `claude-code`

Claude Web, Antigravity, ChatGPT, Gemini, and browser exports are outside V1.

## Commands

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
