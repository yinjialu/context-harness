---
name: init-context
description: Initialize a context-harness personal context home, data directories, global context files, and optional Codex/Claude Code hooks. Use when the user asks to initialize context-harness, set up a personal context system, configure automatic Code Agent conversation backup, or repair context-harness hooks.
license: MIT
---

# Init Context

Use this skill to initialize or repair a `context-harness` installation. The skill can bootstrap the CLI runtime even when only the skill was installed.

## Runtime Bootstrap

Before running `context-harness`, execute the bundled bootstrap script from this skill directory:

```bash
runtime_dir="$(bash scripts/bootstrap.sh)"
cd "$runtime_dir"
```

The script clones or updates the runtime repository at `~/.local/share/context-harness` by default, checks out `v0.1.6`, and runs `uv sync`.

Overrides:

- `CONTEXT_HARNESS_RUNTIME_DIR`: custom runtime checkout path.
- `CONTEXT_HARNESS_REPO_URL`: custom fork URL.
- `CONTEXT_HARNESS_REF`: custom branch, tag, or commit.
- `CONTEXT_HARNESS_BOOTSTRAP_SKIP_UPDATE=1`: skip fetch/pull.

## Workflow

1. Run the Runtime Bootstrap steps above. Use the returned path as the `context-harness` repository root.
2. Choose the data home:
   - Use `CONTEXT_HARNESS_HOME` when set.
   - Use the user's explicit path when provided.
   - Otherwise use `~/.context-harness`.
3. Run all `uv run context-harness ...` commands from the runtime repository root:

```bash
uv run context-harness --context-home <context-home> init
```

4. If the user wants automatic backup hooks, run these commands from the same repository root. Supported Code Agents install to user-level config by default. Use `--scope project` to install into the current project, or combine it with `--project-root` to target another project:

```bash
uv run context-harness --context-home <context-home> hooks install codex
uv run context-harness --context-home <context-home> hooks install codex --scope project
uv run context-harness --context-home <context-home> hooks install codex --scope project --project-root <codex-project-root>
uv run context-harness --context-home <context-home> hooks install claude-code
uv run context-harness --context-home <context-home> hooks install claude-code --scope project
uv run context-harness --context-home <context-home> hooks install claude-code --scope project --project-root <claude-code-project-root>
```

5. Report the data home and hook status.

Do not store user conversations or memory inside the `context-harness` repository unless the user explicitly chooses that path as the data home.
