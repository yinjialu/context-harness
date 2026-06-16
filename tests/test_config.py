from pathlib import Path

from context_harness.config import load_config, resolve_context_home


def test_resolve_context_home_prefers_cli_path(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_HARNESS_HOME", str(tmp_path / "env-home"))

    home = resolve_context_home(cli_context_home=tmp_path / "cli-home")

    assert home == (tmp_path / "cli-home").resolve()


def test_resolve_context_home_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_HARNESS_HOME", str(tmp_path / "env-home"))

    home = resolve_context_home()

    assert home == (tmp_path / "env-home").resolve()


def test_load_config_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTEXT_HARNESS_HOME", raising=False)

    config = load_config(context_home=tmp_path)

    assert config.context_home == tmp_path.resolve()
    assert config.codex.sessions_dir == Path("~/.codex/sessions").expanduser()
    assert config.codex.output_dir == tmp_path / "conversations" / "codex"
    assert config.claude_code.projects_dir == Path("~/.claude/projects").expanduser()
    assert config.claude_code.output_dir == tmp_path / "conversations" / "claude-code"
    assert config.memory.global_context_file == tmp_path / "global-claude.md"
