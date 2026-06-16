import json
from pathlib import Path

from context_harness.cli import main


def test_cli_sync_codex(tmp_path, capsys):
    context_home = tmp_path / "home"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.codex]
enabled = true
sessions_dir = "{sessions}"
output_dir = "conversations/codex"
""",
        encoding="utf-8",
    )

    code = main(["--context-home", str(context_home), "sync", "codex", "--latest", "1"])

    captured = capsys.readouterr()
    assert code == 0
    assert "source=codex" in captured.out
    assert "checked=1" in captured.out
    assert "created=1" in captured.out
    assert list((context_home / "conversations" / "codex").glob("*.md"))


def test_cli_sync_claude_code(tmp_path, capsys):
    context_home = tmp_path / "home"
    projects = tmp_path / "projects"
    projects.mkdir()
    fixture = Path("tests/fixtures/claude-code-session.jsonl").read_text(encoding="utf-8")
    (projects / "claude-code-session-1.jsonl").write_text(fixture, encoding="utf-8")
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.claude-code]
enabled = true
projects_dir = "{projects}"
output_dir = "conversations/claude-code"
""",
        encoding="utf-8",
    )

    code = main(["--context-home", str(context_home), "sync", "claude-code", "--latest", "1"])

    captured = capsys.readouterr()
    assert code == 0
    assert "source=claude-code" in captured.out
    assert "checked=1" in captured.out
    assert "created=1" in captured.out
    assert list((context_home / "conversations" / "claude-code").glob("*.md"))


def test_cli_hooks_install_codex_writes_project_local_config(tmp_path):
    context_home = tmp_path / "home"
    project_root = tmp_path / "project"

    code = main(
        [
            "--context-home",
            str(context_home),
            "hooks",
            "install",
            "codex",
            "--project-root",
            str(project_root),
        ]
    )

    assert code == 0
    assert (project_root / ".codex" / "config.toml").exists()
    hooks = json.loads((project_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "sync codex --latest 1" in command
    assert f"--context-home {context_home}" in command


def test_cli_hooks_install_claude_code_writes_settings(tmp_path):
    context_home = tmp_path / "home"
    settings_path = tmp_path / ".claude" / "settings.json"

    code = main(
        [
            "--context-home",
            str(context_home),
            "hooks",
            "install",
            "claude-code",
            "--claude-settings",
            str(settings_path),
        ]
    )

    assert code == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "sync claude-code --latest 1" in command
    assert f"--context-home {context_home}" in command


def test_cli_dream_prints_skill_hint(capsys):
    code = main(["dream"])

    captured = capsys.readouterr()
    assert code == 0
    assert "profile-dreamer workflow is available through the profile-dreamer skill" in captured.out
