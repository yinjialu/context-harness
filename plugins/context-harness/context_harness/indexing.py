"""Rebuild OKF ``index.md`` / ``log.md`` files across the data home.

This is the IO layer that scans archived conversations, reads their frontmatter,
and (re)writes the OKF index/log files. Index rebuild is decoupled from any
single ``sync``: it always reads the current on-disk state, so it is idempotent
and shared by both the collectors' CLI path and the migration command.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import okf

_RESERVED_NAMES = {"index.md", "log.md"}
_HEADING_RE = re.compile(r"^#\s+(?:\d{4}-\d{2}-\d{2}\s*[-—–]\s*)?(.*)$")


def _archive_files(source_dir: Path) -> list[Path]:
    # Recurse: some adapters nest archives under date subdirectories.
    return sorted(p for p in source_dir.rglob("*.md") if p.name not in _RESERVED_NAMES)


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            title = match.group(1).strip()
            if title:
                return title
    return fallback


def _read_entry(path: Path, source: str, source_dir: Path) -> okf.ConversationEntry | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    fields, body = okf.parse_frontmatter(text)
    title = fields.get("title") or _title_from_body(body or text, path.stem)
    created = fields.get("created")
    messages = fields.get("messages")
    return okf.ConversationEntry(
        filename=path.relative_to(source_dir).as_posix(),
        title=str(title),
        created=str(created) if created is not None else None,
        messages=messages if isinstance(messages, int) else None,
        source=str(fields.get("source") or source),
    )


def _build_root_index(home: Path) -> str:
    extra_links: list[tuple[str, str]] = []
    if (home / "conversations").is_dir():
        extra_links.append(("Conversations", "conversations/index.md"))
    if (home / "memory" / "MEMORY.md").exists():
        extra_links.append(("Memory", "memory/MEMORY.md"))
    if (home / "global-claude.md").exists():
        extra_links.append(("Personal Context", "global-claude.md"))

    return okf.build_dir_index(
        [],
        title="Personal Knowledge Base",
        description="context-harness 个人上下文知识库（OKF 兼容）。",
        extra_links=extra_links,
    )


def plan_indexes(home: Path) -> dict[Path, str]:
    """Compute the desired content of every index/log file under ``home``.

    Reads existing archives but writes nothing; the returned mapping is used by
    both the writer (apply) and dry-run reporting.
    """
    plan: dict[Path, str] = {}
    conversations = home / "conversations"
    source_links: list[tuple[str, str]] = []

    if conversations.is_dir():
        for source_dir in sorted(d for d in conversations.iterdir() if d.is_dir()):
            source = source_dir.name
            entries = [entry for p in _archive_files(source_dir) if (entry := _read_entry(p, source, source_dir))]
            if not entries:
                continue
            plan[source_dir / "index.md"] = okf.build_dir_index(
                entries,
                title=f"{source} conversations",
                description=f"{source} 对话归档（OKF 知识库）。",
            )
            plan[source_dir / "log.md"] = okf.build_conversation_log(
                entries, title=f"{source} conversation log"
            )
            source_links.append((source, f"{source}/index.md"))

        if source_links:
            plan[conversations / "index.md"] = okf.build_dir_index(
                [],
                title="Conversations",
                description="按来源归档的对话知识库。",
                extra_links=source_links,
            )

    plan[home / "index.md"] = _build_root_index(home)
    return plan


def write_plan(plan: dict[Path, str], *, dry_run: bool = False) -> list[Path]:
    """Write only the files whose content changed; return the changed paths."""
    changed: list[Path] = []
    for path, content in plan.items():
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing == content:
            continue
        changed.append(path)
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed


def rebuild_all_indexes(home: Path, *, dry_run: bool = False) -> list[Path]:
    """Rebuild every index/log under ``home``; return paths that changed."""
    return write_plan(plan_indexes(home), dry_run=dry_run)
