from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import okf
from .datetime_utils import local_date, local_isoformat, local_time
from .models import Conversation, Message


def _date(value: datetime) -> str:
    return local_date(value)


def _time(value: datetime | None) -> str:
    if value is None:
        return ""
    return " " + local_time(value)


def _role_label(role: str) -> str:
    if role == "user":
        return "User"
    if role == "assistant":
        return "Assistant"
    return role.title()


def _render_message(message: Message) -> str:
    label = _role_label(message.role)
    return f"### **{label}**{_time(message.created_at)}\n{message.content.strip()}\n"


def _project_name(conversation: Conversation) -> str | None:
    metadata = conversation.metadata
    for key in ("Project", "project"):
        value = metadata.get(key)
        if value:
            return str(value).strip() or None
    for key in ("Cwd", "cwd"):
        value = metadata.get(key)
        if value:
            name = Path(str(value)).name
            if name:
                return name
    return None


def _frontmatter(conversation: Conversation) -> str:
    message_count = len(conversation.messages)
    fields: dict[str, object] = {
        "type": okf.CONVERSATION_TYPE,
        "title": conversation.title,
        "description": okf.conversation_description(
            conversation.source, message_count, _project_name(conversation)
        ),
        "source": conversation.source,
        "session": conversation.session_id,
        "messages": message_count,
        "created": local_isoformat(conversation.created_at),
        "tags": okf.conversation_tags(conversation.source),
        "timestamp": local_isoformat(conversation.synced_at),
    }
    # Remaining metadata is preserved verbatim as producer fields.
    for key, value in conversation.metadata.items():
        fields.setdefault(key, value)
    return okf.render_frontmatter(fields)


def _body(conversation: Conversation) -> str:
    lines = [
        f"# {_date(conversation.created_at)} - {conversation.title}",
        f"- **Source**: {conversation.source}",
        f"- **Session**: `{conversation.session_id}`",
        f"- **Messages**: {len(conversation.messages)}",
        f"- **Synced At**: {local_isoformat(conversation.synced_at)}",
    ]
    for key, value in conversation.metadata.items():
        lines.append(f"- **{key}**: {value}")
    lines.append("---")
    lines.append("")
    lines.extend(_render_message(message) for message in conversation.messages)
    return "\n".join(lines).rstrip() + "\n"


def render_conversation(conversation: Conversation) -> str:
    """Render a conversation as an OKF-compliant markdown archive: an OKF
    frontmatter block on top, the original human-readable body unchanged below."""
    return _frontmatter(conversation) + "\n" + _body(conversation)
