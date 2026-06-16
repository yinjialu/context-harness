---
name: profile-dreamer
description: Review context-harness conversation archives and propose durable memory/profile updates. Use when the user asks to dream, update memory, refresh their profile, extract personal context from conversations, or maintain the context-harness memory loop.
---

# Profile Dreamer

Use this skill to review archived conversations and propose memory/profile updates.

## Workflow

1. Resolve the context home from `CONTEXT_HARNESS_HOME`, the user's explicit path, or `~/.context-harness`.
2. Read:
   - `state/dream-state.json`
   - `global-claude.md`
   - `memory/user_profile.md`
   - new or changed files under `conversations/`
3. Extract durable signals:
   - identity changes
   - technical preferences
   - recurring working style
   - active projects
   - writing/content direction
   - explicit instructions for AI agents
4. Present a reviewable proposal grouped by add/update/strengthen/deprecate.
5. Wait for user confirmation before writing memory files.
6. After confirmation, update:
   - `global-claude.md`
   - `memory/user_profile.md`
   - `logs/dream.md`
   - `state/dream-state.json`

Do not silently rewrite memory/profile files.
