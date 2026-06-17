from pathlib import Path

import pytest

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
    assert config.hermes_agent.sessions_dir == Path("~/.hermes/sessions").expanduser()
    assert config.hermes_agent.output_dir == tmp_path / "conversations" / "hermes-agent"
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

[sources.hermes-agent]
sessions_dir = "fixtures/hermes"
output_dir = "exports/hermes"

[memory]
profile_file = "memory/profile.md"
global_context_file = "{global_context_file}"
""",
        encoding="utf-8",
    )

    config = load_config(context_home=tmp_path)

    assert config.codex.sessions_dir == Path("~/context-harness-codex").expanduser()
    assert config.codex.output_dir == codex_output_dir
    assert config.claude_code.projects_dir == tmp_path / "fixtures" / "claude"
    assert config.claude_code.output_dir == tmp_path / "exports" / "claude"
    assert config.hermes_agent.sessions_dir == tmp_path / "fixtures" / "hermes"
    assert config.hermes_agent.output_dir == tmp_path / "exports" / "hermes"
    assert config.memory.profile_file == tmp_path / "memory/profile.md"
    assert config.memory.global_context_file == global_context_file


@pytest.mark.parametrize(
    ("path_kind", "configured_path", "expected_path"),
    [
        ("relative", "fixtures/matrix", "context_home:fixtures/matrix"),
        ("absolute", "absolute-matrix", "absolute-matrix"),
        ("home", "~/context-harness-matrix", "home:~/context-harness-matrix"),
    ],
)
@pytest.mark.parametrize(
    ("config_body", "actual_path"),
    [
        (
            "[sources.codex]\nsessions_dir = {configured_path}\n",
            lambda config: config.codex.sessions_dir,
        ),
        (
            "[sources.claude-code]\noutput_dir = {configured_path}\n",
            lambda config: config.claude_code.output_dir,
        ),
        (
            "[sources.hermes-agent]\nsessions_dir = {configured_path}\n",
            lambda config: config.hermes_agent.sessions_dir,
        ),
        (
            "[memory]\nprofile_file = {configured_path}\n",
            lambda config: config.memory.profile_file,
        ),
    ],
    ids=["source-input", "source-output", "hermes-source-input", "memory"],
)
def test_load_config_resolves_path_matrix(
    tmp_path,
    monkeypatch,
    path_kind,
    configured_path,
    expected_path,
    config_body,
    actual_path,
):
    monkeypatch.delenv("CONTEXT_HARNESS_HOME", raising=False)
    if path_kind == "absolute":
        configured_path = str(tmp_path / configured_path)
        expected = Path(configured_path)
    elif path_kind == "home":
        expected = Path(expected_path.removeprefix("home:")).expanduser()
    else:
        expected = tmp_path / expected_path.removeprefix("context_home:")
    (tmp_path / "config.toml").write_text(
        config_body.format(configured_path=repr(configured_path)),
        encoding="utf-8",
    )

    config = load_config(context_home=tmp_path)

    assert actual_path(config) == expected