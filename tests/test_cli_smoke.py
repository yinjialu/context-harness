from context_harness.cli import main


def test_cli_help_returns_zero(capsys):
    code = main(["--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "context-harness" in captured.out
    assert "init" in captured.out
    assert "sync" in captured.out
    assert "hooks" in captured.out


def test_cli_requires_top_level_command():
    assert main([]) == 2


def test_cli_hooks_requires_nested_command():
    assert main(["hooks"]) == 2
