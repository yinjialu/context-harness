from datetime import datetime, timezone

from context_harness import okf
from context_harness.markdown import render_conversation
from context_harness.migrate import migrate_okf
from context_harness.models import Conversation, Message


def _home(tmp_path):
    home = tmp_path / "home"
    (home / "conversations" / "antigravity").mkdir(parents=True)
    (home / "conversations" / "codex").mkdir(parents=True)
    (home / "memory").mkdir(parents=True)
    return home


def _legacy_conversation(path):
    path.write_text(
        "# 2026-03-25 — Publishing Harness Engineering Article\n\n"
        "- **Source**: Antigravity Local API\n"
        "- **ID**: `2232f3cb-9db0-4b05-ad27-d6f4f5207172`\n"
        "- **Messages**: 4 user inputs\n"
        "- **Project**: `yinjialu/Engineer`\n\n"
        "---\n\n"
        "### **User**\nhello\n",
        encoding="utf-8",
    )


def test_migrate_adds_frontmatter_to_legacy_conversation(tmp_path):
    home = _home(tmp_path)
    archive = home / "conversations" / "antigravity" / "20260325_2232f3cb.md"
    _legacy_conversation(archive)

    migrate_okf(home)

    fields, body = okf.parse_frontmatter(archive.read_text(encoding="utf-8"))
    assert fields["type"] == "Conversation"
    assert fields["title"] == "Publishing Harness Engineering Article"
    assert fields["source"] == "antigravity"
    assert fields["session"] == "2232f3cb-9db0-4b05-ad27-d6f4f5207172"
    assert fields["messages"] == 4
    assert fields["tags"] == ["conversation", "antigravity"]
    assert "project Engineer" in fields["description"] or "yinjialu/Engineer" in fields["description"]
    # Original body is preserved below the frontmatter.
    assert "- **Source**: Antigravity Local API" in body
    assert "### **User**" in body


def test_migrate_is_noop_on_writer_output(tmp_path):
    home = _home(tmp_path)
    conversation = Conversation(
        source="codex",
        session_id="abc",
        title="一个会话",
        created_at=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 8, 30, tzinfo=timezone.utc),
        messages=[Message(role="user", content="hi", created_at=datetime(2026, 6, 16, 8, 1, tzinfo=timezone.utc))],
        metadata={"Cwd": "/tmp/project"},
    )
    archive = home / "conversations" / "codex" / "20260616_abc.md"
    original = render_conversation(conversation)
    archive.write_text(original, encoding="utf-8")

    changed = migrate_okf(home)

    assert archive.read_text(encoding="utf-8") == original
    assert archive not in changed


def test_migrate_memory_normalizes_experience_document_to_insight(tmp_path):
    home = _home(tmp_path)
    mem = home / "memory" / "insight_antigravity_backup.md"
    mem.write_text(
        "---\nid: insight_antigravity_backup\ntitle: 揭秘提取会话流\ntype: experience_document\n---\n\n正文\n",
        encoding="utf-8",
    )

    migrate_okf(home)

    fields, body = okf.parse_frontmatter(mem.read_text(encoding="utf-8"))
    assert fields["type"] == "insight"
    assert fields["name"] == "insight_antigravity_backup"
    assert fields["title"] == "揭秘提取会话流"
    assert "timestamp" in fields
    assert "正文" in body


def test_migrate_memory_preserves_producer_fields_and_adds_missing(tmp_path):
    home = _home(tmp_path)
    mem = home / "memory" / "feedback_article_reviewer.md"
    mem.write_text(
        "---\nname: article-reviewer\ndescription: 反馈沉淀\ntype: feedback\noriginSessionId: 0b579849\n---\n正文\n",
        encoding="utf-8",
    )

    migrate_okf(home)

    fields, _ = okf.parse_frontmatter(mem.read_text(encoding="utf-8"))
    assert fields["type"] == "feedback"
    assert fields["originSessionId"] == "0b579849"
    assert "title" in fields
    assert "tags" in fields
    assert "timestamp" in fields


def test_migrate_memory_index_gets_index_type(tmp_path):
    home = _home(tmp_path)
    index = home / "memory" / "MEMORY.md"
    index.write_text("# Memory\n\n- [User Profile](user_profile.md) — 画像\n", encoding="utf-8")

    migrate_okf(home)

    fields, body = okf.parse_frontmatter(index.read_text(encoding="utf-8"))
    assert fields["type"] == "Index"
    assert "[User Profile](user_profile.md)" in body


def test_migrate_global_context(tmp_path):
    home = _home(tmp_path)
    gc = home / "global-claude.md"
    gc.write_text("# 关于我\n\n尹家露，携程 AI 技术部。\n", encoding="utf-8")

    migrate_okf(home)

    fields, body = okf.parse_frontmatter(gc.read_text(encoding="utf-8"))
    assert fields["type"] == "Personal Context"
    assert "title" in fields
    assert "# 关于我" in body


def test_migrate_dry_run_reports_without_writing(tmp_path):
    home = _home(tmp_path)
    archive = home / "conversations" / "antigravity" / "20260325_2232f3cb.md"
    _legacy_conversation(archive)
    original = archive.read_text(encoding="utf-8")

    changed = migrate_okf(home, dry_run=True)

    assert archive in changed
    assert archive.read_text(encoding="utf-8") == original


def test_migrate_is_idempotent(tmp_path):
    home = _home(tmp_path)
    _legacy_conversation(home / "conversations" / "antigravity" / "20260325_2232f3cb.md")
    (home / "memory" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (home / "memory" / "project_x.md").write_text(
        "---\nname: x\ndescription: d\ntype: project\n---\n正文\n", encoding="utf-8"
    )
    (home / "global-claude.md").write_text("# 关于我\n\n内容\n", encoding="utf-8")

    first = migrate_okf(home)
    second = migrate_okf(home)

    assert first
    assert second == []


def test_migrate_nested_conversation_uses_top_level_source(tmp_path):
    home = _home(tmp_path)
    nested = home / "conversations" / "qoderwork" / "2026-05-15" / "session-summary.md"
    nested.parent.mkdir(parents=True)
    nested.write_text(
        "---\nplatform: qoderwork\nsession_date: 2026-05-15\n---\n\n# Session Summary\n",
        encoding="utf-8",
    )

    migrate_okf(home)

    fields, _ = okf.parse_frontmatter(nested.read_text(encoding="utf-8"))
    assert fields["source"] == "qoderwork"
    assert fields["tags"] == ["conversation", "qoderwork"]
    assert fields["platform"] == "qoderwork"  # producer field preserved
    # Nested archive is reachable from the source index.
    index = (home / "conversations" / "qoderwork" / "index.md").read_text(encoding="utf-8")
    assert "(2026-05-15/session-summary.md)" in index


def test_migrate_rebuilds_indexes(tmp_path):
    home = _home(tmp_path)
    _legacy_conversation(home / "conversations" / "antigravity" / "20260325_2232f3cb.md")

    migrate_okf(home)

    assert (home / "conversations" / "antigravity" / "index.md").exists()
    assert (home / "conversations" / "index.md").exists()
    assert (home / "index.md").exists()
