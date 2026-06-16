from __future__ import annotations

import json
import re
from hashlib import sha1
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message, SyncResult
from context_harness.state import read_state, write_state


def _parse_time(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "conversation"


def _message_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def _event_title(event: dict[str, Any]) -> str:
    for key in ("title", "summary", "content"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value

    payload = event.get("message")
    if isinstance(payload, dict):
        return _message_content(payload)
    return ""


def _read_claude_code_session(path: Path) -> Conversation | None:
    session_id = path.stem
    title = path.stem
    created_at: datetime | None = None
    messages: list[Message] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        if not line.strip():
            continue
        try:
            event: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_time = _parse_time(event.get("timestamp"))
        event_type = event.get("type")
        raw_session_id = event.get("sessionId")
        if isinstance(raw_session_id, str) and raw_session_id:
            session_id = raw_session_id

        if event_type in {"summary", "ai-title", "custom-title"}:
            event_title = _event_title(event)
            if event_title.strip():
                title = event_title
            created_at = event_time or created_at
            continue

        if event_type not in {"user", "assistant"}:
            continue
        if event.get("isMeta") is True:
            continue

        payload = event.get("message")
        if not isinstance(payload, dict):
            continue

        raw_role = payload.get("role")
        role = raw_role if raw_role in {"user", "assistant"} else event_type
        content = _message_content(payload)
        if not content.strip():
            continue

        if created_at is None:
            created_at = event_time
        messages.append(Message(role=role, content=content, created_at=event_time))

    if not messages:
        return None

    return Conversation(
        source="claude-code",
        session_id=session_id,
        title=title,
        created_at=created_at or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        synced_at=datetime.now(UTC),
        messages=messages,
    )


def _source_key(projects_dir: Path, source_path: Path, conversation: Conversation) -> str:
    try:
        relative_path = source_path.relative_to(projects_dir)
    except ValueError:
        relative_path = source_path
    return f"{conversation.session_id}:{relative_path.as_posix()}"


def _archive_path(output_dir: Path, conversation: Conversation, source_path: Path, source_key: str) -> Path:
    date = conversation.created_at.strftime("%Y-%m-%d")
    short_id = _safe_name(conversation.session_id)[:32]
    source_stem = _safe_name(source_path.stem)[:40]
    source_digest = sha1(source_key.encode("utf-8")).hexdigest()[:10]
    slug = _safe_name(conversation.title)[:80]
    name = "-".join(part for part in [date, short_id, source_stem, source_digest, slug] if part)
    return output_dir / f"{name}.md"


def sync_claude_code(
    projects_dir: Path,
    output_dir: Path,
    state_path: Path,
    latest: int | None = None,
    all_sessions: bool = False,
    session_path: Path | None = None,
) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if session_path is not None:
        session_files = [session_path] if session_path.exists() and session_path.suffix == ".jsonl" else []
    elif not projects_dir.exists():
        return SyncResult("claude-code", 0, 0, 0, 0, str(output_dir))
    else:
        session_files = sorted(projects_dir.rglob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
        if latest is not None and not all_sessions:
            session_files = session_files[:latest]

    state = read_state(state_path)
    claude_code_state = state.setdefault("claude-code", {})
    checked = created = updated = skipped = 0

    for session_file in session_files:
        checked += 1
        conversation = _read_claude_code_session(session_file)
        if conversation is None:
            continue

        source_key = _source_key(projects_dir, session_file, conversation)
        archive_path = _archive_path(output_dir, conversation, session_file, source_key)
        message_count = len(conversation.messages)
        previous = claude_code_state.get(source_key, {})

        if previous.get("message_count") == message_count and archive_path.exists():
            skipped += 1
            continue

        existed = archive_path.exists()
        archive_path.write_text(render_conversation(conversation), encoding="utf-8")
        claude_code_state[source_key] = {
            "archive": archive_path.name,
            "message_count": message_count,
            "source_path": str(session_file),
        }
        if existed or previous:
            updated += 1
        else:
            created += 1

    write_state(state_path, state)
    return SyncResult("claude-code", checked, created, updated, skipped, str(output_dir))
