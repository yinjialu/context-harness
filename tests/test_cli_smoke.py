from context_harness.cli import main


def test_cli_help_returns_zero(capsys):
    code = main(["--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "context-harness" in captured.out
    assert "init" in captured.out
    assert "sync" in captured.out
    assert "hooks" in captured.out
