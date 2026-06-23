from context_harness import okf


def test_render_frontmatter_basic_fields_in_order():
    rendered = okf.render_frontmatter(
        {
            "type": "Conversation",
            "title": "帮我启动这个项目",
            "messages": 30,
            "tags": ["conversation", "claude-code"],
        }
    )

    assert rendered.startswith("---\n")
    assert rendered.endswith("---\n")
    assert "type: Conversation\n" in rendered
    assert "title: 帮我启动这个项目\n" in rendered
    assert "messages: 30\n" in rendered
    assert "tags: [conversation, claude-code]\n" in rendered
    # Field order is preserved.
    assert rendered.index("type:") < rendered.index("title:") < rendered.index("messages:")


def test_render_frontmatter_skips_none_and_empty():
    rendered = okf.render_frontmatter(
        {"type": "Index", "title": None, "description": "", "tags": []}
    )

    assert "title:" not in rendered
    assert "description:" not in rendered
    assert "tags:" not in rendered
    assert "type: Index\n" in rendered


def test_render_frontmatter_quotes_values_that_need_it():
    rendered = okf.render_frontmatter(
        {
            "type": "Conversation",
            "title": "key: value pair",
            "session": "42",
            "note": "true",
        }
    )

    assert 'title: "key: value pair"\n' in rendered
    # Pure-int strings round-trip as ints; quoted only when ambiguous.
    assert 'session: "42"\n' in rendered
    assert 'note: "true"\n' in rendered


def test_render_frontmatter_int_renders_bare():
    rendered = okf.render_frontmatter({"type": "Conversation", "messages": 7})
    assert "messages: 7\n" in rendered


def test_parse_frontmatter_round_trip():
    text = (
        "---\n"
        "type: Conversation\n"
        "title: 帮我启动这个项目\n"
        "messages: 30\n"
        "tags: [conversation, claude-code]\n"
        "---\n"
        "\n"
        "# body heading\n"
        "content\n"
    )

    fields, body = okf.parse_frontmatter(text)

    assert fields["type"] == "Conversation"
    assert fields["title"] == "帮我启动这个项目"
    assert fields["messages"] == 30
    assert fields["tags"] == ["conversation", "claude-code"]
    assert body == "\n# body heading\ncontent\n"


def test_parse_frontmatter_no_frontmatter_returns_empty_fields():
    text = "# Just a heading\n\nbody\n"
    fields, body = okf.parse_frontmatter(text)
    assert fields == {}
    assert body == text


def test_parse_frontmatter_unquotes_quoted_values():
    text = '---\ntype: Conversation\ntitle: "key: value"\n---\nbody\n'
    fields, _ = okf.parse_frontmatter(text)
    assert fields["title"] == "key: value"


def test_render_then_parse_is_stable():
    fields = {
        "type": "Conversation",
        "title": "揭秘：如何提取会话流",
        "description": "claude-code · 30 messages · project context-harness",
        "messages": 30,
        "tags": ["conversation", "claude-code"],
        "created": "2026-05-10T09:56:12+08:00",
    }
    rendered = okf.render_frontmatter(fields)
    parsed, _ = okf.parse_frontmatter(rendered + "body\n")
    assert parsed == fields
    # Re-rendering the parsed fields is a fixed point.
    assert okf.render_frontmatter(parsed) == rendered


def test_conversation_description_with_project():
    assert (
        okf.conversation_description("claude-code", 30, "AuraCare")
        == "claude-code · 30 messages · project AuraCare"
    )


def test_conversation_description_without_project():
    assert okf.conversation_description("codex", 1, None) == "codex · 1 messages"


def test_conversation_tags():
    assert okf.conversation_tags("claude-code") == ["conversation", "claude-code"]


def test_build_dir_index_lists_entries_with_links():
    entries = [
        okf.ConversationEntry(
            filename="20260510_5dc7bc0c.md",
            title="帮我启动这个项目",
            created="2026-05-10T09:56:12+08:00",
            messages=30,
        ),
        okf.ConversationEntry(
            filename="20260509_abcd1234.md",
            title="另一个会话",
            created="2026-05-09T10:00:00+08:00",
            messages=5,
        ),
    ]

    index = okf.build_dir_index(
        entries, title="claude-code conversations", description="claude-code 归档索引"
    )

    assert index.startswith("---\n")
    assert "type: Index\n" in index
    assert "title: claude-code conversations\n" in index
    # Newest first, markdown relative links.
    assert "[帮我启动这个项目](20260510_5dc7bc0c.md)" in index
    assert "[另一个会话](20260509_abcd1234.md)" in index
    assert index.index("20260510_5dc7bc0c.md") < index.index("20260509_abcd1234.md")


def test_build_conversation_log_is_reverse_chronological():
    entries = [
        okf.ConversationEntry(filename="a.md", title="A", created="2026-05-09T10:00:00+08:00", messages=5),
        okf.ConversationEntry(filename="b.md", title="B", created="2026-05-10T10:00:00+08:00", messages=8),
    ]

    log = okf.build_conversation_log(entries, title="claude-code log")

    assert "type: Log\n" in log
    # B (newer) appears before A (older).
    assert log.index("b.md") < log.index("a.md")
