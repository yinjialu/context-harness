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


def test_load_config_resolves_custom_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTEXT_HARNESS_HOME", raising=False)
    codex_output_dir = tmp_path / "absolute-codex-output"
    global_context_file = tmp_path / "absolute-global-claude.md"
    (tmp_path / "config.toml").write_text(
        f"""
[sources.codex]
sessions_dir = "~/context-harness-codex"
output_dir = "{codex_output_dir}"

[sources.claude-code]
projects_dir = "fixtures/claude"
output_dir = "exports/claude"

[memory]
profile_file = "memory/profile.md"
global_context_file = "{global_context_file}"
""",
        encoding="utf-8",
    )

    config = load_config(context_home=tmp_path)

    assert config.codex.sessions_dir == Path("~/context-harness-codex").expanduser()
    assert config.codex.output_dir == codex_output_dir
    assert config.claude_code.projects_dir == tmp_path / "fixtures/claude"
    assert config.claude_code.output_dir == tmp_path / "exports/claude"
    assert config.memory.profile_file == tmp_path / "memory/profile.md"
    assert config.memory.global_context_file == global_context_file
