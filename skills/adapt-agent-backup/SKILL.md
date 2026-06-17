---
name: adapt-agent-backup
description: Implement a new local Code Agent conversation backup adapter in context-harness. Use when asked to add support for backing up another AI coding assistant, adapt a new Agent source, create collectors/hooks/config/tests for a new context-harness source, or prepare a PR that lets context-harness sync a currently unsupported Agent.
license: MIT
---

# Adapt Agent Backup

Use this skill when adding support for a new Code Agent source to `context-harness`.

## First Read

Before editing, read:

- `docs/agent-backup-adapter-architecture.md`
- Existing collectors in `context_harness/collectors/`
- Existing tests for Codex and Claude Code in `tests/`

## Workflow

1. Identify the source id.
   - Use lowercase kebab-case, for example `my-agent`.
   - Derive the id from the target Agent name unless the user explicitly provides one.
   - Use the same id in config, CLI, output directories, state keys, tests, and docs.

2. Check whether the source is already supported.
   - Search for the source id and common aliases in `context_harness/`, `tests/`, `skills/`, `README.md`, and `README.zh-CN.md`.
   - Inspect `context_harness/cli.py` sync choices, `context_harness/config.py`, `context_harness/init.py`, `context_harness/collectors/`, and `context_harness/hooks/`.
   - If support is complete, do not add a duplicate adapter. Instead, verify it with existing tests or a smoke command, then report that the source is already supported.
   - If support is partial or broken, repair only the missing or failing pieces and preserve the existing source id and archive/state compatibility.

3. Inspect the target Agent's local transcript format.
   - Find default transcript paths.
   - Identify session id, title, timestamps, roles, user messages, assistant messages, tool/noise events, and internal meta events.
   - Check whether the Agent has a reliable stop/session hook. If not, implement manual sync only.
   - Use synthetic or anonymized fixtures only.

4. Add config and initialization.
   - Update `context_harness/config.py` with a new source in `AppConfig` and `load_config`.
   - Update `context_harness/init.py` with default config and `conversations/<source>` directory creation.

5. Add a collector.
   - Create `context_harness/collectors/<source>.py`.
   - Parse raw transcript files into `Conversation` and `Message`.
   - Ignore bad JSON lines, empty messages, tools, and internal metadata.
   - Return `None` for sessions with no user-visible conversation.
   - Reuse `render_conversation`, `read_state`, `write_state`, and the existing `SyncResult` pattern.
   - Support `latest`, `all_sessions`, and `session_path`.

6. Register CLI commands.
   - Add the source to `sync` choices in `context_harness/cli.py`.
   - Dispatch to `sync_<source>`.
   - Respect `enabled = false` with `_disabled_result`.

7. Add hooks only when reliable.
   - Create `context_harness/hooks/<source>.py` only if the Agent has a stable hook/config mechanism.
   - Hook commands should call `sync <source> --hook-stdin`.
   - Preserve unrelated user settings and make hook installation idempotent.
   - Register hook install support in `context_harness/cli.py`.

8. Update docs and skills.
   - Update `README.md` and `README.zh-CN.md`.
   - Add the source to the supported local AI coding assistants list in both README files.
   - Prefer the target Agent's official product/docs URL for the link.
   - Prefer an official favicon/logo URL from the Agent's website or docs for the icon; if no reliable official icon URL exists, use a plain text link instead of adding an unofficial asset.
   - Update `skills/init-context/SKILL.md` and `skills/sync-conversations/SKILL.md`.
   - Keep skills as workflow instructions; keep behavior in the CLI.

9. Add focused tests.
   - Add fixtures under `tests/fixtures/`.
   - Cover config defaults/custom paths, init directories/default config, collector archive output, skipped unchanged archives, missing source directory, latest mtime behavior, hook `session_path` override, noise filtering, bad JSON tolerance, filename stability, CLI sync, disabled source behavior, and hook idempotence if hooks are implemented.

10. Verify.
   - Run `uv sync` if dependencies are not installed.
   - Run `uv run pytest`.
   - Manually smoke test `uv run context-harness --context-home <tmp-home> sync <source> --latest 1` when a fixture or local sample is available.
   - Keep changes small and complete; do not refactor unrelated modules.

## PR Checklist

- The adapter produces Markdown archives in `context_home/conversations/<source>/`.
- The adapter writes incremental state to `context_home/state/<source>-sync-state.json`.
- README supported-Agent lists, examples, default config, skills, CLI choices, and tests all use the same source id.
- Real user transcripts, memory, logs, state, and private machine config are not committed.
- PR description states transcript format assumptions, hook support status, commands run, and remaining risks.
- The diff avoids unrelated rewrites and leaves existing behavior intact outside the new adapter path.
