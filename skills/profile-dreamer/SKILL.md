---
name: profile-dreamer
description: Review context-harness conversation archives and propose durable memory/profile updates. Use when the user asks to dream, update memory, refresh their profile, extract personal context from conversations, or maintain the context-harness memory loop.
license: MIT
---

# Profile Dreamer

Use this skill to review archived conversations and propose memory/profile updates. The skill can bootstrap the CLI runtime even when only the skill was installed.

## Runtime Bootstrap

Before using local context-harness files or commands, execute the bundled bootstrap script from this skill directory:

```bash
runtime_dir="$(bash scripts/bootstrap.sh)"
cd "$runtime_dir"
```

The script clones or updates the runtime repository at `~/.local/share/context-harness` by default, checks out `v0.1.4`, and runs `uv sync`.

Overrides:

- `CONTEXT_HARNESS_RUNTIME_DIR`: custom runtime checkout path.
- `CONTEXT_HARNESS_REPO_URL`: custom fork URL.
- `CONTEXT_HARNESS_REF`: custom branch, tag, or commit.
- `CONTEXT_HARNESS_BOOTSTRAP_SKIP_UPDATE=1`: skip fetch/pull.

## Workflow

1. Run the Runtime Bootstrap steps above so the local CLI/templates are available.
2. Resolve the context home from `CONTEXT_HARNESS_HOME`, the user's explicit path, or `~/.context-harness`.
3. Read:
   - `state/dream-state.json`
   - `global-claude.md`
   - `memory/user_profile.md`
   - new or changed files under `conversations/`
4. Extract durable signals:
   - identity changes
   - technical preferences
   - recurring working style
   - active projects
   - writing/content direction
   - explicit instructions for AI agents
5. Present a reviewable proposal grouped by add/update/strengthen/deprecate.
6. Wait for user confirmation before writing memory files.
7. After confirmation, update:
   - `global-claude.md`
   - `memory/user_profile.md`
   - `logs/dream.md`
   - `state/dream-state.json`

Do not silently rewrite memory/profile files.
