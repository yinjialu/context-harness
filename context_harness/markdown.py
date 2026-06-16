from __future__ import annotations

from datetime import datetime

from .models import Conversation, Message


def _date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _time(value: datetime | None) -> str:
    if value is None:
        return ""
    return " " + value.strftime("%H:%M")


def _role_label(role: str) -> str:
    if role == "user":
        return "User"
    if role == "assistant":
        return "Assistant"
    return role.title()


def _render_message(message: Message) -> str:
    label = _role_label(message.role)
    return f"### **{label}**{_time(message.created_at)}\n{message.content.strip()}\n"


def render_conversation(conversation: Conversation) -> str:
    lines = [
        f"# {_date(conversation.created_at)} - {conversation.title}",
        f"- **Source**: {conversation.source}",
        f"- **Session**: `{conversation.session_id}`",
        f"- **Messages**: {len(conversation.messages)}",
        f"- **Synced At**: {conversation.synced_at.isoformat()}",
    ]
    for key, value in conversation.metadata.items():
        lines.append(f"- **{key}**: {value}")
    lines.append("---")
    lines.append("")
    lines.extend(_render_message(message) for message in conversation.messages)
    return "\n".join(lines).rstrip() + "\n"
