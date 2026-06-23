from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import okf
from .config import resolve_context_home
from .indexing import rebuild_all_indexes


MEMORY_INDEX_TEMPLATE = (
    okf.render_frontmatter(
        {
            "type": okf.INDEX_TYPE,
            "title": "Memory",
            "description": "memory 知识库索引。",
            "tags": ["index", "memory"],
        }
    )
    + "\n# Memory\n"
)

USER_PROFILE_TEMPLATE = (
    okf.render_frontmatter(
        {
            "type": "user",
            "name": "user-profile",
            "title": "User Profile",
            "description": "个人画像 — 背景、技术栈、工作方式。",
            "tags": ["user"],
        }
    )
    + "\n# User Profile\n"
)

GLOBAL_CONTEXT_TEMPLATE = (
    okf.render_frontmatter(
        {
            "type": "Personal Context",
            "title": "关于我",
            "description": "个人画像、工作方式与个人上下文系统入口。",
            "tags": ["profile", "personal-context"],
        }
    )
    + "\n# Personal Context\n\nSee `memory/` for detailed context.\n"
)


DEFAULT_CONFIG_TEMPLATE = """[paths]
context_home = {context_home}

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
"""


LINK_MARKER = "<!-- context-harness: personal global context -->"
LINK_END_MARKER = "<!-- /context-harness: personal global context -->"
CODEX_LINK_MARKER = "<!-- context-harness: codex personal global context -->"
CODEX_LINK_END_MARKER = "<!-- /context-harness: codex personal global context -->"


def _default_claude_md() -> Path:
    """Resolved lazily so callers (and tests) that override ``Path.home`` are honored."""
    return Path.home() / ".claude" / "CLAUDE.md"


def _default_codex_agents_md() -> Path:
    """Resolved lazily so callers (and tests) that override ``Path.home`` are honored."""
    return Path.home() / ".codex" / "AGENTS.md"


@dataclass(frozen=True)
class InitResult:
    context_home: Path
    statuses: dict[str, str]


def _write_if_missing(path: Path, content: str, statuses: dict[str, str]) -> None:
    if path.exists():
        statuses[path.name] = "unchanged"
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    statuses[path.name] = "created"


def _default_config(home: Path) -> str:
    return DEFAULT_CONFIG_TEMPLATE.format(context_home=json.dumps(str(home)))


def _ensure_config_context_home(path: Path, home: Path, statuses: dict[str, str]) -> None:
    if not path.exists():
        _write_if_missing(path, _default_config(home), statuses)
        return

    desired_line = f"context_home = {json.dumps(str(home))}"
    lines = path.read_text(encoding="utf-8").splitlines()
    in_paths = False
    paths_header_index: int | None = None
    context_home_index: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_paths = stripped == "[paths]"
            if in_paths:
                paths_header_index = index
            continue
        if in_paths and stripped.startswith("context_home"):
            context_home_index = index
            break

    if context_home_index is not None:
        if lines[context_home_index].strip() == desired_line:
            statuses[path.name] = "unchanged"
            return
        lines[context_home_index] = desired_line
    elif paths_header_index is not None:
        lines.insert(paths_header_index + 1, desired_line)
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[paths]", desired_line])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    statuses[path.name] = "updated"


def _remove_managed_blocks(content: str, start_marker: str, end_marker: str) -> str:
    lines = content.splitlines()
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != start_marker:
            cleaned.append(lines[i])
            i += 1
            continue

        end_index = None
        for candidate in range(i + 1, len(lines)):
            if lines[candidate].strip() == end_marker:
                end_index = candidate
                break

        if end_index is not None:
            i = end_index + 1
        elif i + 1 < len(lines) and lines[i + 1].strip().startswith("@"):
            i += 2
        else:
            i += 1

        if i < len(lines) and not lines[i].strip():
            i += 1

    return "\n".join(cleaned).rstrip()


def _append_block(existing: str, block: str) -> str:
    cleaned = existing.rstrip()
    if cleaned:
        return f"{cleaned}\n\n{block}"
    return block


def link_claude_global_context(
    global_context_file: Path,
    claude_md_path: Path,
    statuses: dict[str, str],
) -> None:
    """Idempotently add an `@import` of the global context file into Claude Code's
    user-level CLAUDE.md. Non-destructive: existing content is preserved."""
    target = global_context_file.resolve()
    import_line = f"@{target}"

    existing = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
    if any(line.strip() == import_line for line in existing.splitlines()) and existing.count(LINK_MARKER) <= 1:
        statuses[claude_md_path.name] = "unchanged"
        return
    cleaned = _remove_managed_blocks(existing, LINK_MARKER, LINK_END_MARKER)
    if any(line.strip() == import_line for line in cleaned.splitlines()):
        if cleaned != existing.rstrip():
            claude_md_path.write_text(f"{cleaned}\n" if cleaned else "", encoding="utf-8")
            statuses[claude_md_path.name] = "linked"
            return
        statuses[claude_md_path.name] = "unchanged"
        return

    block = f"{LINK_MARKER}\n{import_line}\n{LINK_END_MARKER}\n"
    new_content = _append_block(cleaned, block)

    claude_md_path.parent.mkdir(parents=True, exist_ok=True)
    claude_md_path.write_text(new_content, encoding="utf-8")
    statuses[claude_md_path.name] = "linked"


def link_codex_global_context(
    global_context_file: Path,
    codex_agents_path: Path,
    statuses: dict[str, str],
) -> None:
    """Idempotently add a Codex global AGENTS.md pointer to the context-harness
    global context entry. Codex reads AGENTS.md, but it does not import @paths."""
    target = global_context_file.resolve()
    existing = codex_agents_path.read_text(encoding="utf-8") if codex_agents_path.exists() else ""
    cleaned = _remove_managed_blocks(existing, CODEX_LINK_MARKER, CODEX_LINK_END_MARKER)
    target_text = str(target)
    if target_text in existing and existing.count(CODEX_LINK_MARKER) <= 1:
        statuses[codex_agents_path.name] = "unchanged"
        return
    if target_text in cleaned:
        if cleaned != existing.rstrip():
            codex_agents_path.write_text(f"{cleaned}\n" if cleaned else "", encoding="utf-8")
            statuses[codex_agents_path.name] = "linked"
            return
        statuses[codex_agents_path.name] = "unchanged"
        return

    block = (
        f"{CODEX_LINK_MARKER}\n"
        "## Context Harness Memory\n\n"
        f"At the start of each new Codex session, read `{target}` for durable personal context.\n\n"
        "Treat it as user-level memory. Current user messages and higher-priority instructions still win.\n"
        f"{CODEX_LINK_END_MARKER}\n"
    )
    new_content = _append_block(cleaned, block)

    codex_agents_path.parent.mkdir(parents=True, exist_ok=True)
    codex_agents_path.write_text(new_content, encoding="utf-8")
    statuses[codex_agents_path.name] = "linked"


def initialize_context_home(
    context_home: str | Path | None = None,
    *,
    claude_md_path: Path | None = None,
    codex_agents_path: Path | None = None,
) -> InitResult:
    home = resolve_context_home(context_home)
    statuses: dict[str, str] = {}

    for directory in [
        home / "conversations" / "codex",
        home / "conversations" / "claude-code",
        home / "memory",
        home / "logs",
        home / "state",
        home / "exports",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    _ensure_config_context_home(home / "config.toml", home, statuses)
    _write_if_missing(home / "memory" / "MEMORY.md", MEMORY_INDEX_TEMPLATE, statuses)
    _write_if_missing(home / "memory" / "user_profile.md", USER_PROFILE_TEMPLATE, statuses)
    global_context_file = home / "global-claude.md"
    _write_if_missing(global_context_file, GLOBAL_CONTEXT_TEMPLATE, statuses)

    # Scaffold the OKF root index (and any conversation indexes from existing
    # archives). Idempotent: re-running over an unchanged home is a no-op.
    index_changed = rebuild_all_indexes(home)
    statuses["index.md"] = "created" if index_changed else "unchanged"

    link_claude_global_context(
        global_context_file,
        claude_md_path if claude_md_path is not None else _default_claude_md(),
        statuses,
    )
    link_codex_global_context(
        global_context_file,
        codex_agents_path if codex_agents_path is not None else _default_codex_agents_md(),
        statuses,
    )

    return InitResult(context_home=home, statuses=statuses)
