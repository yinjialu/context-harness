from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class Conversation:
    source: str
    session_id: str
    title: str
    created_at: datetime
    synced_at: datetime
    messages: list[Message]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncResult:
    source: str
    checked: int
    created: int
    updated: int
    skipped: int
    output_dir: str
