from __future__ import annotations

from datetime import datetime


def to_local(value: datetime) -> datetime:
    return value.astimezone()


def local_date(value: datetime) -> str:
    return to_local(value).strftime("%Y-%m-%d")


def local_compact_date(value: datetime) -> str:
    return to_local(value).strftime("%Y%m%d")


def local_time(value: datetime) -> str:
    return to_local(value).strftime("%H:%M")


def local_isoformat(value: datetime) -> str:
    return to_local(value).isoformat()
