import json
import sys
from io import StringIO
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


def test_cli_sync_codex_respects_disabled_source(tmp_path, capsys):
    context_home = tmp_path / "home"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.codex]
enabled = false
sessions_dir = "{sessions}"
output_dir = "conversations/codex"
""",
        encoding="utf-8",
    )

    code = main(["--context-home", str(context_home), "sync", "codex", "--latest", "1"])

    captured = capsys.readouterr()
    assert code == 0
    assert "source=codex checked=0 created=0 updated=0 skipped=0" in captured.out
    assert not (context_home / "conversations" / "codex").exists()


def test_cli_sync_codex_hook_stdin_uses_transcript_path(tmp_path, capsys, monkeypatch):
    context_home = tmp_path / "home"
    sessions = tmp_path / "sessions"
    target = sessions / "target.jsonl"
    newer = sessions / "newer.jsonl"
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    target.parent.mkdir()
    target.write_text(fixture.replace("Context Harness", "Target Session"), encoding="utf-8")
    newer.write_text(fixture.replace("Context Harness", "Newer Session"), encoding="utf-8")
    newer.touch()
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.codex]
enabled = true
sessions_dir = "{sessions}"
output_dir = "conversations/codex"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps({"transcript_path": str(target)})))

    code = main(["--context-home", str(context_home), "sync", "codex", "--hook-stdin"])

    captured = capsys.readouterr()
    assert code == 0
    assert "checked=1" in captured.out
    archive = next((context_home / "conversations" / "codex").glob("*.md"))
    content = archive.read_text(encoding="utf-8")
    assert "Target Session" in content
    assert "Newer Session" not in content


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


def test_cli_sync_claude_code_respects_disabled_source(tmp_path, capsys):
    context_home = tmp_path / "home"
    projects = tmp_path / "projects"
    projects.mkdir()
    fixture = Path("tests/fixtures/claude-code-session.jsonl").read_text(encoding="utf-8")
    (projects / "claude-code-session-1.jsonl").write_text(fixture, encoding="utf-8")
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.claude-code]
enabled = false
projects_dir = "{projects}"
output_dir = "conversations/claude-code"
""",
        encoding="utf-8",
    )

    code = main(["--context-home", str(context_home), "sync", "claude-code", "--latest", "1"])

    captured = capsys.readouterr()
    assert code == 0
    assert "source=claude-code checked=0 created=0 updated=0 skipped=0" in captured.out
    assert not (context_home / "conversations" / "claude-code").exists()


def test_cli_sync_claude_code_hook_stdin_uses_transcript_path(tmp_path, capsys, monkeypatch):
    context_home = tmp_path / "home"
    projects = tmp_path / "projects"
    target = projects / "target.jsonl"
    newer = projects / "newer.jsonl"
    fixture = Path("tests/fixtures/claude-code-session.jsonl").read_text(encoding="utf-8")
    target.parent.mkdir()
    target.write_text(fixture.replace("Context Harness", "Target Session"), encoding="utf-8")
    newer.write_text(fixture.replace("Context Harness", "Newer Session"), encoding="utf-8")
    newer.touch()
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.claude-code]
enabled = true
projects_dir = "{projects}"
output_dir = "conversations/claude-code"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps({"transcript_path": str(target)})))

    code = main(["--context-home", str(context_home), "sync", "claude-code", "--hook-stdin"])

    captured = capsys.readouterr()
    assert code == 0
    assert "checked=1" in captured.out
    archive = next((context_home / "conversations" / "claude-code").glob("*.md"))
    content = archive.read_text(encoding="utf-8")
    assert "Target Session" in content
    assert "Newer Session" not in content


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
    assert "sync codex --hook-stdin" in command
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
    assert "sync claude-code --hook-stdin" in command
    assert f"--context-home {context_home}" in command


def test_cli_dream_prints_skill_hint(capsys):
    code = main(["dream"])

    captured = capsys.readouterr()
    assert code == 0
    assert "profile-dreamer workflow is available through the profile-dreamer skill" in captured.out
