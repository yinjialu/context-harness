---
name: init-context
description: Initialize a context-harness personal context home, data directories, global context files, and optional Codex/Claude Code hooks. Use when the user asks to initialize context-harness, set up a personal context system, configure automatic Code Agent conversation backup, or repair context-harness hooks.
---

# Init Context

Use this skill to initialize or repair a `context-harness` installation.

## Workflow

1. Locate the `context-harness` repository or ask the user for the path.
2. Choose the data home:
   - Use `CONTEXT_HARNESS_HOME` when set.
   - Use the user's explicit path when provided.
   - Otherwise use `~/.context-harness`.
3. Change to the `context-harness` repository root.
4. Before running any command, first locate the `context-harness` repository and change to its repository root. Run all `uv run ...` commands from that root:

```bash
uv run context-harness --context-home <context-home> init
```

5. If the user wants automatic backup hooks, run these commands from the same repository root:

```bash
uv run context-harness --context-home <context-home> hooks install codex
uv run context-harness --context-home <context-home> hooks install claude-code
```

6. Report the data home and hook status.

Do not store user conversations or memory inside the `context-harness` repository unless the user explicitly chooses that path as the data home.
