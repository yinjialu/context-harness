import json

from context_harness.hooks.claude_code import install_claude_code_hook
from context_harness.hooks.codex import install_codex_hook


def test_install_codex_hook_is_idempotent(tmp_path):
    changed = install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")
    unchanged = install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    assert changed is True
    assert unchanged is False
    assert "codex_hooks = true" in (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    hooks = json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "context-harness --context-home" in command
    assert "sync codex --latest 1" in command


def test_install_claude_code_hook_is_idempotent(tmp_path):
    settings_path = tmp_path / "settings.json"

    changed = install_claude_code_hook(settings_path=settings_path, context_home=tmp_path / "home")
    unchanged = install_claude_code_hook(settings_path=settings_path, context_home=tmp_path / "home")

    assert changed is True
    assert unchanged is False
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "context-harness --context-home" in command
    assert "sync claude-code --latest 1" in command
