import json
import shlex

from context_harness.hooks.claude_code import install_claude_code_hook
from context_harness.hooks.codex import install_codex_hook


def _config_lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_install_codex_hook_is_idempotent(tmp_path):
    changed = install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")
    unchanged = install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    assert changed is True
    assert unchanged is False
    assert "hooks = true" in _config_lines(tmp_path / ".codex" / "config.toml")
    hooks = json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    hook = hooks["hooks"]["Stop"][0]["hooks"][0]
    command = hook["command"]
    assert "context-harness --context-home" in command
    assert "sync codex --latest 1" in command
    assert hook["timeout"] == 30
    assert "async" not in hook


def test_install_codex_hook_updates_canonical_feature_flag(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text("[features]\nhooks = false\n", encoding="utf-8")

    install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    config = _config_lines(codex_dir / "config.toml")
    assert "hooks = true" in config
    assert "hooks = false" not in config
    assert sum(line.startswith("hooks") for line in config) == 1


def test_install_codex_hook_recognizes_whitespace_feature_section(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text("[ features ]\nhooks = false\n", encoding="utf-8")

    install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    config = _config_lines(codex_dir / "config.toml")
    assert "[ features ]" in config
    assert "[features]" not in config
    assert "hooks = true" in config
    assert "hooks = false" not in config
    assert sum(line.strip() in {"[ features ]", "[features]"} for line in config) == 1


def test_install_codex_hook_updates_deprecated_feature_flag_without_duplicate(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text("[features]\ncodex_hooks\t= false\n", encoding="utf-8")

    install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    config = _config_lines(codex_dir / "config.toml")
    assert "hooks = true" in config
    assert "codex_hooks = true" in config
    assert "codex_hooks\t= false" not in config
    assert sum(line.startswith("codex_hooks") for line in config) == 1


def test_install_codex_hook_preserves_unrelated_settings_and_updates_old_command(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        'model = "gpt-5"\n[features]\nhooks   = false\nother = true\n[projects.demo]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    (codex_dir / "hooks.json").write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    "Start": [{"hooks": [{"type": "command", "command": "echo start"}]}],
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [
                                {"type": "command", "command": "echo keep"},
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old sync codex --latest 1",
                                },
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    config = (codex_dir / "config.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-5"' in config
    assert "hooks = true" in config.splitlines()
    assert "other = true" in config
    assert "[projects.demo]" in config
    settings = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
    assert settings["version"] == 1
    assert settings["hooks"]["Start"][0]["hooks"][0]["command"] == "echo start"
    stop_commands = [hook["command"] for hook in settings["hooks"]["Stop"][0]["hooks"]]
    assert "echo keep" in stop_commands
    context_hooks = [command for command in stop_commands if "sync codex --latest 1" in command]
    assert len(context_hooks) == 1
    assert "--context-home /old" not in context_hooks[0]
    updated_hook = settings["hooks"]["Stop"][0]["hooks"][1]
    assert updated_hook["timeout"] == 30
    assert "async" not in updated_hook


def test_install_codex_hook_collapses_duplicate_context_harness_hooks(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-a sync codex --latest 1",
                                },
                                {"type": "command", "command": "echo keep"},
                            ],
                        },
                        {
                            "matcher": "other",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-b sync codex --latest 1",
                                },
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-c sync codex --latest 1",
                                },
                            ],
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    install_codex_hook(project_root=tmp_path, context_home=tmp_path / "home")

    settings = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
    stop_hooks = settings["hooks"]["Stop"]
    commands = [
        hook["command"]
        for group in stop_hooks
        for hook in group["hooks"]
        if isinstance(hook, dict) and "command" in hook
    ]
    context_hooks = [command for command in commands if "sync codex --latest 1" in command]
    assert len(context_hooks) == 1
    assert f"--context-home {shlex.quote(str(tmp_path / 'home'))}" in context_hooks[0]
    assert "echo keep" in commands


def test_install_codex_hook_quotes_context_home_with_spaces(tmp_path):
    context_home = tmp_path / "home with spaces"

    install_codex_hook(project_root=tmp_path, context_home=context_home)

    hooks = json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert f"--context-home {shlex.quote(str(context_home))}" in command


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


def test_install_claude_code_hook_preserves_updates_and_quotes_context_home(tmp_path):
    settings_path = tmp_path / "settings.json"
    context_home = tmp_path / "home with spaces"
    settings_path.write_text(
        json.dumps(
            {
                "theme": "dark",
                "hooks": {
                    "PreToolUse": [{"hooks": [{"type": "command", "command": "echo pre"}]}],
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [
                                {"type": "command", "command": "echo keep"},
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old sync claude-code --latest 1",
                                },
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    install_claude_code_hook(settings_path=settings_path, context_home=context_home)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo pre"
    stop_hooks = settings["hooks"]["Stop"][0]["hooks"]
    assert stop_hooks[0]["command"] == "echo keep"
    context_hooks = [hook for hook in stop_hooks if "sync claude-code --latest 1" in hook["command"]]
    assert len(context_hooks) == 1
    assert f"--context-home {shlex.quote(str(context_home))}" in context_hooks[0]["command"]
    assert "--context-home /old" not in context_hooks[0]["command"]
    assert context_hooks[0]["timeout"] == 30
    assert context_hooks[0]["async"] is True


def test_install_claude_code_hook_collapses_duplicate_context_harness_hooks(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-a sync claude-code --latest 1",
                                },
                                {"type": "command", "command": "echo keep"},
                            ],
                        },
                        {
                            "matcher": "other",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-b sync claude-code --latest 1",
                                },
                                {
                                    "type": "command",
                                    "command": "context-harness --context-home /old-c sync claude-code --latest 1",
                                },
                            ],
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    install_claude_code_hook(settings_path=settings_path, context_home=tmp_path / "home")

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["Stop"]
        for hook in group["hooks"]
        if isinstance(hook, dict) and "command" in hook
    ]
    context_hooks = [command for command in commands if "sync claude-code --latest 1" in command]
    assert len(context_hooks) == 1
    assert f"--context-home {shlex.quote(str(tmp_path / 'home'))}" in context_hooks[0]
    assert "echo keep" in commands
