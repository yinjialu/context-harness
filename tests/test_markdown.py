from datetime import datetime, timezone

from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message


def test_render_conversation_markdown():
    conversation = Conversation(
        source="codex",
        session_id="session-123",
        title="Build context harness",
        created_at=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 8, 30, tzinfo=timezone.utc),
        messages=[
            Message(role="user", content="继续", created_at=datetime(2026, 6, 16, 8, 1, tzinfo=timezone.utc)),
            Message(role="assistant", content="好的。", created_at=datetime(2026, 6, 16, 8, 2, tzinfo=timezone.utc)),
        ],
        metadata={"Project": "/tmp/project"},
    )

    rendered = render_conversation(conversation)

    assert rendered.startswith("# 2026-06-16 - Build context harness")
    assert "- **Source**: codex" in rendered
    assert "- **Session**: `session-123`" in rendered
    assert "- **Messages**: 2" in rendered
    assert "- **Project**: /tmp/project" in rendered
    assert "### **User** 08:01" in rendered
    assert "### **Assistant** 08:02" in rendered


def test_render_conversation_uses_local_timezone(set_timezone):
    set_timezone("Asia/Shanghai")
    conversation = Conversation(
        source="codex",
        session_id="session-123",
        title="Build context harness",
        created_at=datetime(2026, 6, 16, 20, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 20, 30, tzinfo=timezone.utc),
        messages=[
            Message(role="user", content="继续", created_at=datetime(2026, 6, 16, 20, 1, tzinfo=timezone.utc)),
        ],
    )

    rendered = render_conversation(conversation)

    assert rendered.startswith("# 2026-06-17 - Build context harness")
    assert "- **Synced At**: 2026-06-17T04:30:00+08:00" in rendered
    assert "### **User** 04:01" in rendered
