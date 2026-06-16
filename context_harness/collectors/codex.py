from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message, SyncResult
from context_harness.state import read_state, write_state


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "conversation"


def _read_codex_session(path: Path) -> Conversation | None:
    session_id = path.stem
    title = path.stem
    cwd = ""
    created_at: datetime | None = None
    messages: list[Message] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event: dict[str, Any] = json.loads(line)
        event_time = _parse_time(event.get("timestamp"))
        payload = event.get("payload") or {}

        if event.get("type") == "session_meta":
            session_id = str(payload.get("id") or session_id)
            title = str(payload.get("title") or title)
            cwd = str(payload.get("cwd") or "")
            created_at = event_time or created_at
            continue

        if event.get("type") != "event_msg":
            continue

        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = str(payload.get("content") or "").strip()
        if not content:
            continue

        if created_at is None:
            created_at = event_time
        messages.append(Message(role=role, content=content, created_at=event_time))

    if not messages:
        return None

    metadata = {"Cwd": cwd} if cwd else {}
    return Conversation(
        source="codex",
        session_id=session_id,
        title=title,
        created_at=created_at or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        synced_at=datetime.now(UTC),
        messages=messages,
        metadata=metadata,
    )


def _archive_path(output_dir: Path, conversation: Conversation) -> Path:
    date = conversation.created_at.strftime("%Y-%m-%d")
    name = _safe_name(f"{date}-{conversation.session_id}-{conversation.title}")
    return output_dir / f"{name}.md"


def sync_codex(
    sessions_dir: Path,
    output_dir: Path,
    state_path: Path,
    latest: int | None = None,
    all_sessions: bool = False,
) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not sessions_dir.exists():
        return SyncResult("codex", 0, 0, 0, 0, str(output_dir))

    session_files = sorted(sessions_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    if latest is not None and not all_sessions:
        session_files = session_files[:latest]

    state = read_state(state_path)
    codex_state = state.setdefault("codex", {})
    checked = created = updated = skipped = 0

    for session_file in session_files:
        conversation = _read_codex_session(session_file)
        if conversation is None:
            continue

        checked += 1
        archive_path = _archive_path(output_dir, conversation)
        message_count = len(conversation.messages)
        previous = codex_state.get(conversation.session_id, {})

        if previous.get("message_count") == message_count and archive_path.exists():
            skipped += 1
            continue

        existed = archive_path.exists()
        archive_path.write_text(render_conversation(conversation), encoding="utf-8")
        codex_state[conversation.session_id] = {
            "archive": archive_path.name,
            "message_count": message_count,
            "source_path": str(session_file),
        }
        if existed or previous:
            updated += 1
        else:
            created += 1

    write_state(state_path, state)
    return SyncResult("codex", checked, created, updated, skipped, str(output_dir))
