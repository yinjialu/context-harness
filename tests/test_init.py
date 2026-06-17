from context_harness.init import initialize_context_home


def test_initialize_context_home_creates_expected_files(tmp_path):
    result = initialize_context_home(tmp_path)

    assert result.context_home == tmp_path.resolve()
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "conversations" / "codex").is_dir()
    assert (tmp_path / "conversations" / "claude-code").is_dir()
    assert (tmp_path / "conversations" / "opencode").is_dir()
    assert (tmp_path / "memory" / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "user_profile.md").exists()
    assert (tmp_path / "global-claude.md").exists()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "state").is_dir()
    assert "created" in result.statuses.values()
    assert f'context_home = "{tmp_path.resolve()}"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_initialize_context_home_is_idempotent(tmp_path):
    initialize_context_home(tmp_path)
    second = initialize_context_home(tmp_path)

    assert second.statuses["config.toml"] == "unchanged"
    assert second.statuses["global-claude.md"] == "unchanged"
