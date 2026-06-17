from context_harness.init import CODEX_LINK_MARKER, LINK_MARKER, initialize_context_home


def _agent_paths(tmp_path):
    return {
        "claude_md_path": tmp_path / "claude" / "CLAUDE.md",
        "codex_agents_path": tmp_path / "codex" / "AGENTS.md",
    }


def test_initialize_context_home_creates_expected_files(tmp_path):
    result = initialize_context_home(tmp_path, **_agent_paths(tmp_path))

    assert result.context_home == tmp_path.resolve()
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "conversations" / "codex").is_dir()
    assert (tmp_path / "conversations" / "claude-code").is_dir()
    assert (tmp_path / "memory" / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "user_profile.md").exists()
    assert (tmp_path / "global-claude.md").exists()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "state").is_dir()
    assert "created" in result.statuses.values()
    assert f'context_home = "{tmp_path.resolve()}"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_initialize_context_home_is_idempotent(tmp_path):
    paths = _agent_paths(tmp_path)
    initialize_context_home(tmp_path, **paths)
    second = initialize_context_home(tmp_path, **paths)

    assert second.statuses["config.toml"] == "unchanged"
    assert second.statuses["global-claude.md"] == "unchanged"
    assert second.statuses["CLAUDE.md"] == "unchanged"
    assert second.statuses["AGENTS.md"] == "unchanged"


def test_initialize_context_home_repairs_stale_config_context_home(tmp_path):
    paths = _agent_paths(tmp_path)
    config_path = tmp_path / "config.toml"
    tmp_path.mkdir(exist_ok=True)
    config_path.write_text(
        """[paths]
context_home = "/Users/jialu/.context-harness"

[sources.codex]
enabled = false
sessions_dir = "~/custom-codex"
output_dir = "conversations/codex"
""",
        encoding="utf-8",
    )

    result = initialize_context_home(tmp_path, **paths)
    second = initialize_context_home(tmp_path, **paths)

    content = config_path.read_text(encoding="utf-8")
    assert result.statuses["config.toml"] == "updated"
    assert second.statuses["config.toml"] == "unchanged"
    assert f'context_home = "{tmp_path.resolve()}"' in content
    assert 'context_home = "/Users/jialu/.context-harness"' not in content
    assert "enabled = false" in content
    assert 'sessions_dir = "~/custom-codex"' in content


def test_initialize_context_home_links_claude_md(tmp_path):
    paths = _agent_paths(tmp_path)
    result = initialize_context_home(tmp_path, **paths)

    assert result.statuses["CLAUDE.md"] == "linked"
    import_line = f"@{(tmp_path / 'global-claude.md').resolve()}"
    assert import_line in paths["claude_md_path"].read_text(encoding="utf-8")


def test_initialize_context_home_links_codex_agents_md(tmp_path):
    paths = _agent_paths(tmp_path)
    result = initialize_context_home(tmp_path, **paths)

    assert result.statuses["AGENTS.md"] == "linked"
    content = paths["codex_agents_path"].read_text(encoding="utf-8")
    assert str((tmp_path / "global-claude.md").resolve()) in content
    assert "At the start of each new Codex session" in content


def test_link_claude_md_is_idempotent(tmp_path):
    paths = _agent_paths(tmp_path)
    claude_md = paths["claude_md_path"]
    initialize_context_home(tmp_path, **paths)
    after_first = claude_md.read_text(encoding="utf-8")

    # Re-run several times: content must be byte-for-byte stable and never accumulate.
    for _ in range(3):
        result = initialize_context_home(tmp_path, **paths)
        assert result.statuses["CLAUDE.md"] == "unchanged"

    final = claude_md.read_text(encoding="utf-8")
    assert final == after_first
    import_line = f"@{(tmp_path / 'global-claude.md').resolve()}"
    assert final.count(import_line) == 1
    assert final.count(LINK_MARKER) == 1


def test_link_claude_md_preserves_existing_content(tmp_path):
    paths = _agent_paths(tmp_path)
    claude_md = paths["claude_md_path"]
    claude_md.parent.mkdir(parents=True)
    claude_md.write_text("# My global memory\n\nSome notes.\n", encoding="utf-8")

    result = initialize_context_home(tmp_path, **paths)
    # Re-run: existing content stays, import is not duplicated.
    initialize_context_home(tmp_path, **paths)

    content = claude_md.read_text(encoding="utf-8")
    assert content.startswith("# My global memory\n\nSome notes.\n")
    assert content.count("# My global memory") == 1
    assert content.count("Some notes.") == 1
    assert content.count(f"@{(tmp_path / 'global-claude.md').resolve()}") == 1
    assert result.statuses["CLAUDE.md"] == "linked"


def test_link_codex_agents_md_is_idempotent(tmp_path):
    paths = _agent_paths(tmp_path)
    codex_agents = paths["codex_agents_path"]
    initialize_context_home(tmp_path, **paths)
    after_first = codex_agents.read_text(encoding="utf-8")

    for _ in range(3):
        result = initialize_context_home(tmp_path, **paths)
        assert result.statuses["AGENTS.md"] == "unchanged"

    final = codex_agents.read_text(encoding="utf-8")
    assert final == after_first
    assert final.count(str((tmp_path / "global-claude.md").resolve())) == 1
    assert final.count(CODEX_LINK_MARKER) == 1


def test_link_codex_agents_md_preserves_existing_content(tmp_path):
    paths = _agent_paths(tmp_path)
    codex_agents = paths["codex_agents_path"]
    codex_agents.parent.mkdir(parents=True)
    codex_agents.write_text("# Working agreements\n\n- Prefer focused tests.\n", encoding="utf-8")

    result = initialize_context_home(tmp_path, **paths)
    initialize_context_home(tmp_path, **paths)

    content = codex_agents.read_text(encoding="utf-8")
    assert content.startswith("# Working agreements\n\n- Prefer focused tests.\n")
    assert content.count("Prefer focused tests.") == 1
    assert content.count(str((tmp_path / "global-claude.md").resolve())) == 1
    assert result.statuses["AGENTS.md"] == "linked"


def test_link_managed_blocks_are_replaced_when_context_home_changes(tmp_path):
    paths = _agent_paths(tmp_path)
    first_home = tmp_path / "first"
    second_home = tmp_path / "second"

    initialize_context_home(first_home, **paths)
    initialize_context_home(second_home, **paths)

    claude_content = paths["claude_md_path"].read_text(encoding="utf-8")
    codex_content = paths["codex_agents_path"].read_text(encoding="utf-8")
    assert str((first_home / "global-claude.md").resolve()) not in claude_content
    assert str((first_home / "global-claude.md").resolve()) not in codex_content
    assert str((second_home / "global-claude.md").resolve()) in claude_content
    assert str((second_home / "global-claude.md").resolve()) in codex_content
