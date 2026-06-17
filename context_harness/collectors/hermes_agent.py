from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_harness.datetime_utils import local_compact_date
from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message, SyncResult
from context_harness.state import read_state, write_state


def _parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "conversation"


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
            continue
        if item.get("type") == "output_text" and isinstance(item.get("content"), str):
            parts.append(item["content"])
    return "\n".join(parts)


def _message_content(message: dict[str, Any]) -> str:
    content = _text_from_content(message.get("content"))
    if content.strip():
        return content

    # Hermes stores provider-native response items for some backends. Preserve
    # only final user-visible assistant text, not reasoning/tool payloads.
    raw_items = message.get("codex_message_items")
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except json.JSONDecodeError:
            raw_items = None
    if not isinstance(raw_items, list):
        return ""

    parts: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(parts)


def _session_objects_from_json(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not raw.strip():
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            return [payload]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict) and isinstance(item.get("messages"), list)]

    sessions: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    session_id = path.stem
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("messages"), list):
            sessions.append(item)
        elif item.get("role") in {"user", "assistant", "tool", "system"}:
            messages.append(item)
            raw_session_id = item.get("session_id")
            if isinstance(raw_session_id, str) and raw_session_id:
                session_id = raw_session_id
    if sessions:
        return sessions
    if messages:
        return [{"id": session_id, "title": session_id, "messages": messages}]
    return []


def _title_for_session(session: dict[str, Any], session_id: str, messages: list[Message]) -> str:
    title = session.get("title")
    if isinstance(title, str) and title.strip() and title.strip() != "—":
        return title.strip()
    for message in messages:
        if message.role == "user" and message.content.strip():
            return message.content.strip().splitlines()[0][:80]
    return session_id


def _read_hermes_session(path: Path, session: dict[str, Any]) -> Conversation | None:
    session_id = str(session.get("id") or path.stem)
    created_at = _parse_time(session.get("started_at"))
    messages: list[Message] = []

    for raw_message in session.get("messages") or []:
        if not isinstance(raw_message, dict):
            continue
        role = raw_message.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _message_content(raw_message)
        if not content.strip():
            continue
        message_time = _parse_time(raw_message.get("timestamp"))
        if created_at is None:
            created_at = message_time
        messages.append(Message(role=role, content=content, created_at=message_time))

    if not messages:
        return None

    metadata: dict[str, str] = {}
    source = session.get("source")
    model = session.get("model")
    cwd = session.get("cwd")
    if isinstance(source, str) and source:
        metadata["Hermes Source"] = source
    if isinstance(model, str) and model:
        metadata["Model"] = model
    if isinstance(cwd, str) and cwd:
        metadata["Cwd"] = cwd

    return Conversation(
        source="hermes-agent",
        session_id=session_id,
        title=_title_for_session(session, session_id, messages),
        created_at=created_at or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        synced_at=datetime.now(UTC),
        messages=messages,
        metadata=metadata,
    )


def _archive_path(output_dir: Path, conversation: Conversation) -> Path:
    date = local_compact_date(conversation.created_at)
    short_id = _safe_name(conversation.session_id)[:8]
    return output_dir / f"{date}_{short_id}.md"


def _remove_stale_archive(output_dir: Path, previous_archive: str | None, archive_path: Path) -> None:
    if not previous_archive or previous_archive == archive_path.name:
        return
    stale_path = output_dir / previous_archive
    if stale_path.exists() and stale_path.is_file():
        stale_path.unlink()


def _source_key(sessions_dir: Path, source_path: Path, conversation: Conversation) -> str:
    try:
        relative_path = source_path.relative_to(sessions_dir)
    except ValueError:
        relative_path = source_path
    return f"{conversation.session_id}:{relative_path.as_posix()}"


def sync_hermes_agent(
    sessions_dir: Path,
    output_dir: Path,
    state_path: Path,
    latest: int | None = None,
    all_sessions: bool = False,
    session_path: Path | None = None,
) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if session_path is not None:
        session_files = [session_path] if session_path.exists() and session_path.suffix in {".jsonl", ".json"} else []
    elif not sessions_dir.exists():
        return SyncResult("hermes-agent", 0, 0, 0, 0, str(output_dir))
    elif sessions_dir.is_file():
        session_files = [sessions_dir] if sessions_dir.suffix in {".jsonl", ".json"} else []
    else:
        session_files = sorted(
            [path for suffix in ("*.jsonl", "*.json") for path in sessions_dir.rglob(suffix)],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if latest is not None and not all_sessions:
            session_files = session_files[:latest]

    state = read_state(state_path)
    hermes_state = state.setdefault("hermes-agent", {})
    checked = created = updated = skipped = 0

    for session_file in session_files:
        checked += 1
        for session in _session_objects_from_json(session_file):
            conversation = _read_hermes_session(session_file, session)
            if conversation is None:
                continue

            source_key = _source_key(sessions_dir, session_file, conversation)
            message_count = len(conversation.messages)
            previous = hermes_state.get(source_key, {})
            archive_path = _archive_path(output_dir, conversation)

            if previous.get("message_count") == message_count and archive_path.exists():
                skipped += 1
                continue

            existed = archive_path.exists()
            archive_path.write_text(render_conversation(conversation), encoding="utf-8")
            _remove_stale_archive(output_dir, previous.get("archive"), archive_path)
            hermes_state[source_key] = {
                "archive": archive_path.name,
                "message_count": message_count,
                "source_path": str(session_file),
            }
            if existed or previous:
                updated += 1
            else:
                created += 1

    write_state(state_path, state)
    return SyncResult("hermes-agent", checked, created, updated, skipped, str(output_dir))
