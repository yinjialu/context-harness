from __future__ import annotations

import json
import re
import sqlite3
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
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)
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


def _json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _message_time(row_time: int | None, payload: dict[str, Any]) -> datetime | None:
    raw_time = payload.get("time")
    if isinstance(raw_time, dict):
        for key in ("created", "completed", "start", "end"):
            parsed = _parse_time(raw_time.get(key))
            if parsed is not None:
                return parsed
    return _parse_time(row_time)


def _part_text(payload: dict[str, Any]) -> str:
    if payload.get("type") != "text":
        return ""
    text = payload.get("text")
    return text if isinstance(text, str) else ""


def _read_opencode_session(db_path: Path, session_id: str) -> Conversation | None:
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error:
        return None

    try:
        session = connection.execute(
            """
            select id, title, directory, agent, model, time_created, time_updated
            from session
            where id = ?
            """,
            (session_id,),
        ).fetchone()
        if session is None:
            return None

        rows = connection.execute(
            """
            select
              message.id as message_id,
              message.time_created as message_time_created,
              message.data as message_data,
              part.id as part_id,
              part.time_created as part_time_created,
              part.data as part_data
            from message
            left join part on part.message_id = message.id
            where message.session_id = ?
            order by message.time_created, message.id, part.time_created, part.id
            """,
            (session_id,),
        ).fetchall()
    except sqlite3.Error:
        connection.close()
        return None
    finally:
        connection.close()

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        message_id = str(row["message_id"])
        item = grouped.setdefault(
            message_id,
            {
                "message_time_created": row["message_time_created"],
                "message_data": row["message_data"],
                "parts": [],
            },
        )
        if row["part_data"] is not None:
            item["parts"].append(row["part_data"])

    messages: list[Message] = []
    created_at = _parse_time(session["time_created"])
    for item in grouped.values():
        message_payload = _json_object(item["message_data"])
        role = message_payload.get("role")
        if role not in {"user", "assistant"}:
            continue

        parts = [_part_text(_json_object(raw_part)) for raw_part in item["parts"]]
        content = "\n".join(part for part in parts if part.strip())
        if not content.strip():
            continue

        message_time = _message_time(item["message_time_created"], message_payload)
        if created_at is None:
            created_at = message_time
        messages.append(Message(role=role, content=content, created_at=message_time))

    if not messages:
        return None

    metadata: dict[str, str] = {}
    for key, label in (("directory", "Directory"), ("agent", "Agent"), ("model", "Model")):
        value = session[key]
        if isinstance(value, str) and value:
            metadata[label] = value

    title = session["title"] if isinstance(session["title"], str) and session["title"].strip() else session_id
    return Conversation(
        source="opencode",
        session_id=session_id,
        title=title,
        created_at=created_at or datetime.fromtimestamp(db_path.stat().st_mtime, tz=UTC),
        synced_at=datetime.now(UTC),
        messages=messages,
        metadata=metadata,
    )


def _archive_path(output_dir: Path, conversation: Conversation) -> Path:
    date = local_compact_date(conversation.created_at)
    short_id = _safe_name(conversation.session_id)[:16]
    return output_dir / f"{date}_{short_id}.md"


def _remove_stale_archive(output_dir: Path, previous_archive: str | None, archive_path: Path) -> None:
    if not previous_archive or previous_archive == archive_path.name:
        return
    stale_path = output_dir / previous_archive
    if stale_path.exists() and stale_path.is_file():
        stale_path.unlink()


def _database_path(data_dir: Path, session_path: Path | None = None) -> Path | None:
    if session_path is not None:
        if session_path.is_file() and session_path.name.endswith(".db"):
            return session_path
        if session_path.is_dir():
            candidate = session_path / "opencode.db"
            return candidate if candidate.exists() else None
        return None

    if data_dir.is_file() and data_dir.name.endswith(".db"):
        return data_dir
    candidate = data_dir / "opencode.db"
    return candidate if candidate.exists() else None


def _session_ids(db_path: Path, latest: int | None, all_sessions: bool) -> list[str]:
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = connection.execute("select id from session order by time_updated desc, id desc").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        connection.close()

    ids = [str(row[0]) for row in rows]
    if latest is not None and not all_sessions:
        return ids[:latest]
    return ids


def sync_opencode(
    data_dir: Path,
    output_dir: Path,
    state_path: Path,
    latest: int | None = None,
    all_sessions: bool = False,
    session_path: Path | None = None,
) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = _database_path(data_dir, session_path)
    if db_path is None or not db_path.exists():
        return SyncResult("opencode", 0, 0, 0, 0, str(output_dir))

    state = read_state(state_path)
    opencode_state = state.setdefault("opencode", {})
    checked = created = updated = skipped = 0

    for session_id in _session_ids(db_path, latest, all_sessions):
        checked += 1
        conversation = _read_opencode_session(db_path, session_id)
        if conversation is None:
            continue

        message_count = len(conversation.messages)
        previous = opencode_state.get(conversation.session_id, {})
        archive_path = _archive_path(output_dir, conversation)

        if previous.get("message_count") == message_count and archive_path.exists():
            skipped += 1
            continue

        existed = archive_path.exists()
        archive_path.write_text(render_conversation(conversation), encoding="utf-8")
        _remove_stale_archive(output_dir, previous.get("archive"), archive_path)
        opencode_state[conversation.session_id] = {
            "archive": archive_path.name,
            "message_count": message_count,
            "source_path": str(db_path),
        }
        if existed or previous:
            updated += 1
        else:
            created += 1

    write_state(state_path, state)
    return SyncResult("opencode", checked, created, updated, skipped, str(output_dir))
