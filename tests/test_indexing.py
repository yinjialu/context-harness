from context_harness import indexing, okf


def _archive(path, *, title, created, messages, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = {
        "type": "Conversation",
        "title": title,
        "source": source,
        "messages": messages,
        "created": created,
        "tags": ["conversation", source],
    }
    path.write_text(okf.render_frontmatter(fields) + "\n# body\n", encoding="utf-8")


def _make_home(tmp_path):
    home = tmp_path / "home"
    _archive(
        home / "conversations" / "codex" / "20260510_aaaa.md",
        title="较新会话",
        created="2026-05-10T09:00:00+08:00",
        messages=30,
        source="codex",
    )
    _archive(
        home / "conversations" / "codex" / "20260509_bbbb.md",
        title="较旧会话",
        created="2026-05-09T09:00:00+08:00",
        messages=5,
        source="codex",
    )
    _archive(
        home / "conversations" / "claude-code" / "20260511_cccc.md",
        title="claude 会话",
        created="2026-05-11T09:00:00+08:00",
        messages=12,
        source="claude-code",
    )
    (home / "memory").mkdir(parents=True, exist_ok=True)
    (home / "memory" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (home / "global-claude.md").write_text("# 关于我\n", encoding="utf-8")
    return home


def test_rebuild_creates_source_index_and_log(tmp_path):
    home = _make_home(tmp_path)
    indexing.rebuild_all_indexes(home)

    codex_index = (home / "conversations" / "codex" / "index.md").read_text(encoding="utf-8")
    fields, _ = okf.parse_frontmatter(codex_index)
    assert fields["type"] == "Index"
    assert "[较新会话](20260510_aaaa.md)" in codex_index
    assert "[较旧会话](20260509_bbbb.md)" in codex_index
    # Newest first.
    assert codex_index.index("20260510_aaaa.md") < codex_index.index("20260509_bbbb.md")

    codex_log = (home / "conversations" / "codex" / "log.md").read_text(encoding="utf-8")
    log_fields, _ = okf.parse_frontmatter(codex_log)
    assert log_fields["type"] == "Log"


def test_rebuild_creates_conversations_and_root_index(tmp_path):
    home = _make_home(tmp_path)
    indexing.rebuild_all_indexes(home)

    conv_index = (home / "conversations" / "index.md").read_text(encoding="utf-8")
    assert "[codex](codex/index.md)" in conv_index
    assert "[claude-code](claude-code/index.md)" in conv_index

    root_index = (home / "index.md").read_text(encoding="utf-8")
    root_fields, _ = okf.parse_frontmatter(root_index)
    assert root_fields["type"] == "Index"
    assert "(conversations/index.md)" in root_index
    assert "(memory/MEMORY.md)" in root_index
    assert "(global-claude.md)" in root_index


def test_rebuild_is_idempotent(tmp_path):
    home = _make_home(tmp_path)
    first = indexing.rebuild_all_indexes(home)
    second = indexing.rebuild_all_indexes(home)

    assert first  # first run writes files
    assert second == []  # second run is a no-op


def test_rebuild_dry_run_does_not_write(tmp_path):
    home = _make_home(tmp_path)
    planned = indexing.rebuild_all_indexes(home, dry_run=True)

    assert planned  # reports files that would change
    assert not (home / "conversations" / "codex" / "index.md").exists()


def test_rebuild_reads_legacy_archive_without_frontmatter(tmp_path):
    home = tmp_path / "home"
    legacy_dir = home / "conversations" / "antigravity"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "20260325_2232f3cb.md").write_text(
        "# 2026-03-25 — Publishing Article\n\n- **Source**: Antigravity Local API\n",
        encoding="utf-8",
    )

    indexing.rebuild_all_indexes(home)

    index = (legacy_dir / "index.md").read_text(encoding="utf-8")
    assert "Publishing Article" in index
    assert "(20260325_2232f3cb.md)" in index
