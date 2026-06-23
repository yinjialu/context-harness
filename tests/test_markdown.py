from datetime import datetime, timezone

from context_harness import okf
from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message


def _conversation(**overrides):
    base = dict(
        source="codex",
        session_id="session-123",
        title="Build context harness",
        created_at=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 8, 30, tzinfo=timezone.utc),
        messages=[
            Message(role="user", content="继续", created_at=datetime(2026, 6, 16, 8, 1, tzinfo=timezone.utc)),
            Message(role="assistant", content="好的。", created_at=datetime(2026, 6, 16, 8, 2, tzinfo=timezone.utc)),
        ],
        metadata={"Cwd": "/Users/jialu/Documents/AuraCare"},
    )
    base.update(overrides)
    return Conversation(**base)


def test_render_conversation_has_okf_frontmatter():
    rendered = render_conversation(_conversation())
    fields, body = okf.parse_frontmatter(rendered)

    assert fields["type"] == "Conversation"
    assert fields["title"] == "Build context harness"
    assert fields["source"] == "codex"
    assert fields["session"] == "session-123"
    assert fields["messages"] == 2
    assert fields["tags"] == ["conversation", "codex"]
    assert fields["created"] == "2026-06-16T08:00:00+00:00"
    assert fields["timestamp"] == "2026-06-16T08:30:00+00:00"
    # Body is unchanged: heading + bullet metadata block survive below frontmatter.
    assert body.lstrip().startswith("# 2026-06-16 - Build context harness")
    assert "- **Source**: codex" in body
    assert "### **User** 08:01" in body
    assert "### **Assistant** 08:02" in body


def test_render_conversation_description_includes_project_from_cwd():
    rendered = render_conversation(_conversation())
    fields, _ = okf.parse_frontmatter(rendered)
    assert fields["description"] == "codex · 2 messages · project AuraCare"


def test_render_conversation_description_without_project():
    rendered = render_conversation(_conversation(metadata={}))
    fields, _ = okf.parse_frontmatter(rendered)
    assert fields["description"] == "codex · 2 messages"


def test_render_conversation_keeps_metadata_as_producer_fields():
    rendered = render_conversation(_conversation(metadata={"Cwd": "/tmp/project"}))
    fields, _ = okf.parse_frontmatter(rendered)
    assert fields["Cwd"] == "/tmp/project"


def test_render_conversation_uses_local_timezone(set_timezone):
    set_timezone("Asia/Shanghai")
    conversation = _conversation(
        created_at=datetime(2026, 6, 16, 20, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 20, 30, tzinfo=timezone.utc),
        messages=[Message(role="user", content="继续", created_at=datetime(2026, 6, 16, 20, 1, tzinfo=timezone.utc))],
    )

    rendered = render_conversation(conversation)
    fields, body = okf.parse_frontmatter(rendered)

    assert fields["created"] == "2026-06-17T04:00:00+08:00"
    assert fields["timestamp"] == "2026-06-17T04:30:00+08:00"
    assert "# 2026-06-17 - Build context harness" in body
    assert "### **User** 04:01" in body


def test_render_conversation_is_migration_stable():
    """The writer output must already be OKF-compliant: re-parsing and
    re-rendering its frontmatter is a fixed point (migrate-okf is a no-op)."""
    rendered = render_conversation(_conversation())
    fields, _ = okf.parse_frontmatter(rendered)
    assert okf.render_frontmatter(fields) + "\n" in rendered
