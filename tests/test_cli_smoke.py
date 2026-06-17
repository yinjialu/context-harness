import os
import subprocess
import sys
from pathlib import Path

from context_harness.cli import main


def test_cli_help_returns_zero(capsys):
    code = main(["--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "context-harness" in captured.out
    assert "init" in captured.out
    assert "sync" in captured.out
    assert "hooks" in captured.out


def test_cli_version_returns_project_version(capsys):
    code = main(["--version"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "context-harness 0.1.8"


def test_cli_requires_top_level_command():
    assert main([]) == 2


def test_cli_hooks_requires_nested_command():
    assert main(["hooks"]) == 2


def test_module_entrypoint_help_returns_zero():
    result = subprocess.run(
        [sys.executable, "-m", "context_harness", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "context-harness" in result.stdout


def test_console_script_help_returns_zero(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        ["uv", "run", "context-harness", "--help"],
        cwd=repo_root,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(tmp_path / "venv")},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "context-harness" in result.stdout
