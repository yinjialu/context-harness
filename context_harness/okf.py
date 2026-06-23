"""Open Knowledge Format (OKF) primitives.

Pure functions only: data structures in, markdown strings out. No IO, so the
whole module is trivially unit-testable and freely reusable by the conversation
writer, the index builders and the migration command.

OKF v0.1 in one paragraph: a knowledge base is a directory of markdown files,
each carrying a YAML frontmatter block whose only mandatory field is ``type``.
Concepts are linked with ordinary relative markdown links. ``index.md`` and
``log.md`` are optional reserved filenames for progressive disclosure and change
history. This module renders exactly that subset of YAML we emit ourselves, with
a tolerant parser for reading back our own output and pre-existing frontmatter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

CONVERSATION_TYPE = "Conversation"
INDEX_TYPE = "Index"
LOG_TYPE = "Log"

_FENCE = "---"

# Match a leading frontmatter block: "---\n", lazily everything up to a closing
# "---" line, then an optional trailing newline. Group 1 is the inner block.
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)^---[ \t]*\n?", re.DOTALL | re.MULTILINE)

_INT_RE = re.compile(r"-?\d+")
_NUMERIC_RE = re.compile(r"[+-]?(\d[\d_]*)(\.\d+)?([eE][+-]?\d+)?")
_RESERVED_WORDS = {"true", "false", "null", "none", "yes", "no", "on", "off", "~"}
_LEADING_SPECIALS = set("!&*?|>%@`\"'#,[]{}:- ")


# --------------------------------------------------------------------------- #
# Scalar rendering / quoting
# --------------------------------------------------------------------------- #
def _needs_quote(value: str) -> bool:
    if value == "":
        return True
    if value.strip() != value:
        return True
    if value.lower() in _RESERVED_WORDS:
        return True
    if value[0] in _LEADING_SPECIALS:
        return True
    if ": " in value or value.endswith(":") or " #" in value:
        return True
    if "\n" in value or "\r" in value:
        return True
    if _NUMERIC_RE.fullmatch(value):
        return True
    return False


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return f'"{escaped}"'


def _render_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return _quote(text) if _needs_quote(text) else text


def _render_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_scalar(item) for item in value) + "]"
    return _render_scalar(value)


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    return False


def render_frontmatter(fields: Mapping[str, object]) -> str:
    """Render an ordered mapping as a YAML frontmatter block.

    ``None``, empty strings and empty lists are skipped. Lists render in flow
    style (``[a, b]``). The output always opens and closes with a ``---`` fence
    and ends with a newline.
    """
    lines = [_FENCE]
    for key, value in fields.items():
        if _is_empty(value):
            continue
        lines.append(f"{key}: {_render_value(value)}")
    lines.append(_FENCE)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        inner = token[1:-1]
        if token[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return inner
    return token


def _parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    return _parse_scalar(raw)


def _parse_scalar(raw: str) -> object:
    if raw and raw[0] in "\"'":
        return _unquote(raw)
    if _INT_RE.fullmatch(raw):
        return int(raw)
    return raw


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split ``text`` into (frontmatter fields, body).

    Returns ``({}, text)`` when there is no leading frontmatter block. Values
    are parsed into ``str``/``int``/``list`` so that re-rendering them is a fixed
    point (idempotent migration relies on this).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    fields: dict[str, object] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        fields[key.strip()] = _parse_value(raw)

    return fields, text[match.end():]


# --------------------------------------------------------------------------- #
# Conversation helpers (shared by writer + migration)
# --------------------------------------------------------------------------- #
def conversation_description(source: str, messages: int, project: str | None) -> str:
    base = f"{source} · {messages} messages"
    if project:
        return f"{base} · project {project}"
    return base


def conversation_tags(source: str) -> list[str]:
    return ["conversation", source]


@dataclass(frozen=True)
class ConversationEntry:
    """Lightweight record describing one archived conversation, used to build
    ``index.md`` and ``log.md`` without re-reading message bodies."""

    filename: str
    title: str
    created: str | None = None
    messages: int | None = None
    source: str | None = None


def _sort_entries(entries: Sequence[ConversationEntry]) -> list[ConversationEntry]:
    # Newest first; entries without a timestamp sort last but stay stable.
    return sorted(entries, key=lambda e: (e.created or "", e.filename), reverse=True)


def _entry_meta(entry: ConversationEntry) -> str:
    parts: list[str] = []
    if entry.source:
        parts.append(entry.source)
    if entry.created:
        parts.append(entry.created)
    if entry.messages is not None:
        parts.append(f"{entry.messages} messages")
    return " · ".join(parts)


def build_dir_index(
    entries: Sequence[ConversationEntry],
    *,
    title: str,
    description: str,
    timestamp: str | None = None,
    extra_links: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Build an OKF ``index.md`` listing conversation entries newest-first.

    ``extra_links`` are ``(label, target)`` pairs rendered before the entries,
    used by the conversations/root indexes to point at sub-knowledge-bases.
    """
    fields = {
        "type": INDEX_TYPE,
        "title": title,
        "description": description,
        "tags": ["index"],
        "timestamp": timestamp,
    }
    lines = [render_frontmatter(fields), f"# {title}", ""]
    if description:
        lines.append(description)
        lines.append("")

    if extra_links:
        for label, target in extra_links:
            lines.append(f"- [{label}]({target})")
        lines.append("")

    for entry in _sort_entries(entries):
        meta = _entry_meta(entry)
        suffix = f" — {meta}" if meta else ""
        lines.append(f"- [{entry.title}]({entry.filename}){suffix}")

    return "\n".join(lines).rstrip() + "\n"


def build_conversation_log(
    entries: Sequence[ConversationEntry],
    *,
    title: str,
    timestamp: str | None = None,
) -> str:
    """Build an OKF ``log.md``: a reverse-chronological timeline of entries."""
    fields = {
        "type": LOG_TYPE,
        "title": title,
        "description": "Reverse-chronological change history.",
        "tags": ["log"],
        "timestamp": timestamp,
    }
    lines = [render_frontmatter(fields), f"# {title}", ""]
    for entry in _sort_entries(entries):
        when = entry.created or "?"
        count = f" ({entry.messages} messages)" if entry.messages is not None else ""
        lines.append(f"- {when} — [{entry.title}]({entry.filename}){count}")

    return "\n".join(lines).rstrip() + "\n"
