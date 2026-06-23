"""Idempotent migration of an existing data home to OKF.

Adds/repairs OKF frontmatter on conversations, memory files and the global
context file, then rebuilds all index/log files. Re-running produces no diff:
unknown producer fields are preserved, only missing standard fields are filled,
and human-authored bodies are never touched.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from . import indexing, okf
from .datetime_utils import local_isoformat

_MEMORY_TYPES = {"user", "project", "feedback", "reference", "insight"}
_TYPE_ALIASES = {"experience_document": "insight"}
_RESERVED_NAMES = {"index.md", "log.md"}
_SLUG_RE = re.compile(r"[a-z0-9]+([-_][a-z0-9]+)*")
_HEADING_RE = re.compile(r"^#\s+(?:\d{4}-\d{2}-\d{2}\s*[-—–]\s*)?(.*)$")


# --------------------------------------------------------------------------- #
# Small parsing helpers (legacy bodies)
# --------------------------------------------------------------------------- #
def _mtime_iso(path: Path) -> str:
    return local_isoformat(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))


def _title_from_body(text: str, fallback: str) -> str:
    for line in text.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match and match.group(1).strip():
            return match.group(1).strip()
    return fallback


def _bullet(text: str, *labels: str) -> str | None:
    for label in labels:
        match = re.search(rf"^- \*\*{re.escape(label)}\*\*:\s*(.+?)\s*$", text, re.MULTILINE)
        if match:
            return match.group(1).strip().strip("`").strip()
    return None


def _leading_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"\d+", value)
    return int(match.group(0)) if match else None


def _date_from_heading(text: str) -> str | None:
    match = re.search(r"^#\s+(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    return match.group(1) if match else None


def _humanize(name: str) -> str:
    if _SLUG_RE.fullmatch(name):
        return name.replace("-", " ").replace("_", " ").title()
    return name


# --------------------------------------------------------------------------- #
# Field builders (one per knowledge type)
# --------------------------------------------------------------------------- #
def _producer_extras(fields: dict[str, object], consumed: set[str]) -> dict[str, object]:
    return {key: value for key, value in fields.items() if key not in consumed}


def _conversation_fields(fields: dict[str, object], body: str, path: Path, source: str) -> dict[str, object]:
    legacy = path.read_text(encoding="utf-8") if not fields else body
    title = fields.get("title") or _title_from_body(legacy, path.stem)
    session = fields.get("session") or _bullet(legacy, "Session", "ID")
    messages = fields.get("messages")
    if not isinstance(messages, int):
        messages = _leading_int(_bullet(legacy, "Messages")) or 0
    created = fields.get("created") or _bullet(legacy, "Created") or _date_from_heading(legacy) or _mtime_iso(path)
    description = fields.get("description")
    if not description:
        project = _bullet(legacy, "Project")
        if project:
            project = project.split("/")[-1]
        description = okf.conversation_description(source, messages, project)
    timestamp = fields.get("timestamp") or _bullet(legacy, "Synced At") or _mtime_iso(path)

    consumed = {"type", "title", "description", "source", "session", "messages", "created", "tags", "timestamp"}
    result: dict[str, object] = {
        "type": okf.CONVERSATION_TYPE,
        "title": str(title),
        "description": description,
        # The top-level directory under conversations/ is the authoritative source.
        "source": source,
        "session": session,
        "messages": messages,
        "created": created,
        "tags": fields.get("tags") or okf.conversation_tags(source),
        "timestamp": timestamp,
    }
    result.update(_producer_extras(fields, consumed))
    return result


def _memory_fields(fields: dict[str, object], path: Path) -> dict[str, object]:
    raw_type = str(fields.get("type") or "reference")
    type_value = _TYPE_ALIASES.get(raw_type, raw_type)
    name = fields.get("name") or fields.get("id") or path.stem
    title = fields.get("title") or _humanize(str(name))
    timestamp = fields.get("timestamp") or _mtime_iso(path)

    consumed = {"type", "name", "title", "description", "tags", "timestamp", "id"}
    result: dict[str, object] = {
        "type": type_value,
        "name": str(name),
        "title": str(title),
        "description": fields.get("description") or "",
        "tags": fields.get("tags") or [type_value],
        "timestamp": timestamp,
    }
    result.update(_producer_extras(fields, consumed))
    return result


def _index_fields(fields: dict[str, object], path: Path, *, title: str, description: str) -> dict[str, object]:
    consumed = {"type", "title", "description", "tags", "timestamp"}
    result: dict[str, object] = {
        "type": okf.INDEX_TYPE,
        "title": str(fields.get("title") or title),
        "description": str(fields.get("description") or description),
        "tags": fields.get("tags") or ["index"],
        "timestamp": fields.get("timestamp") or _mtime_iso(path),
    }
    result.update(_producer_extras(fields, consumed))
    return result


def _global_context_fields(fields: dict[str, object], body: str, path: Path) -> dict[str, object]:
    consumed = {"type", "title", "description", "tags", "timestamp"}
    title = fields.get("title") or _title_from_body(body, "关于我")
    result: dict[str, object] = {
        "type": "Personal Context",
        "title": str(title),
        "description": str(fields.get("description") or "个人画像、工作方式与个人上下文系统入口。"),
        "tags": fields.get("tags") or ["profile", "personal-context"],
        "timestamp": fields.get("timestamp") or _mtime_iso(path),
    }
    result.update(_producer_extras(fields, consumed))
    return result


# --------------------------------------------------------------------------- #
# File-level migration
# --------------------------------------------------------------------------- #
def _render(fields: dict[str, object], body: str) -> str:
    return (okf.render_frontmatter(fields) + "\n" + body.lstrip("\n")).rstrip("\n") + "\n"


def _apply(path: Path, new_text: str, dry_run: bool, changed: list[Path]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == new_text:
        return
    changed.append(path)
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")


def _migrate_conversation(path: Path, source: str, dry_run: bool, changed: list[Path]) -> None:
    text = path.read_text(encoding="utf-8")
    fields, body = okf.parse_frontmatter(text)
    body = body if fields else text
    new_fields = _conversation_fields(fields, body, path, source)
    _apply(path, _render(new_fields, body), dry_run, changed)


def _migrate_memory(path: Path, dry_run: bool, changed: list[Path]) -> None:
    fields, body = okf.parse_frontmatter(path.read_text(encoding="utf-8"))
    _apply(path, _render(_memory_fields(fields, path), body), dry_run, changed)


def _migrate_index(path: Path, dry_run: bool, changed: list[Path], *, title: str, description: str) -> None:
    fields, body = okf.parse_frontmatter(path.read_text(encoding="utf-8"))
    new_fields = _index_fields(fields, path, title=title, description=description)
    _apply(path, _render(new_fields, body), dry_run, changed)


def _migrate_global_context(path: Path, dry_run: bool, changed: list[Path]) -> None:
    fields, body = okf.parse_frontmatter(path.read_text(encoding="utf-8"))
    _apply(path, _render(_global_context_fields(fields, body, path), body), dry_run, changed)


def migrate_okf(home: Path, *, dry_run: bool = False) -> list[Path]:
    """Migrate ``home`` to OKF in place. Returns the files that changed (or, in
    dry-run mode, the files that would change). Idempotent."""
    home = Path(home)
    changed: list[Path] = []

    conversations = home / "conversations"
    if conversations.is_dir():
        for path in sorted(conversations.rglob("*.md")):
            if path.name in _RESERVED_NAMES:
                continue
            source = path.relative_to(conversations).parts[0]
            _migrate_conversation(path, source, dry_run, changed)

    memory = home / "memory"
    if memory.is_dir():
        for path in sorted(memory.glob("*.md")):
            if path.name == "MEMORY.md":
                _migrate_index(path, dry_run, changed, title="Memory", description="memory 知识库索引。")
            else:
                _migrate_memory(path, dry_run, changed)

    global_context = home / "global-claude.md"
    if global_context.exists():
        _migrate_global_context(global_context, dry_run, changed)

    changed.extend(indexing.rebuild_all_indexes(home, dry_run=dry_run))
    return changed
