from __future__ import annotations

import json
import shlex
from pathlib import Path


_SYNC_MARKER = "sync claude-code --latest 1"


def install_claude_code_hook(settings_path: Path, context_home: Path) -> bool:
    command = (
        f"context-harness --context-home {shlex.quote(str(context_home))} "
        "sync claude-code --latest 1 >/tmp/context-harness-claude-code.log 2>&1 || true"
    )

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    return _ensure_stop_command_hook(settings_path, command)


def _ensure_stop_command_hook(settings_path: Path, command: str) -> bool:
    original = _load_json_object(settings_path)
    updated = json.loads(json.dumps(original))

    hooks = updated.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])
    if not isinstance(stop_hooks, list):
        stop_hooks = []
        hooks["Stop"] = stop_hooks

    if _update_existing_command(stop_hooks, command):
        return _write_if_changed(settings_path, original, updated)

    target_group = _first_hook_group(stop_hooks)
    target_group.setdefault("hooks", []).append(_command_hook(command))
    return _write_if_changed(settings_path, original, updated)


def _load_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _command_hook(command: str) -> dict:
    return {
        "type": "command",
        "command": command,
        "timeout": 30,
        "async": True,
    }


def _update_existing_command(stop_hooks: list, command: str) -> bool:
    found = False
    for group in stop_hooks:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []):
            if not isinstance(hook, dict):
                continue
            existing_command = hook.get("command")
            if isinstance(existing_command, str) and _SYNC_MARKER in existing_command:
                hook.update(_command_hook(command))
                found = True
    return found


def _first_hook_group(stop_hooks: list) -> dict:
    for group in stop_hooks:
        if isinstance(group, dict):
            hooks = group.setdefault("hooks", [])
            if not isinstance(hooks, list):
                group["hooks"] = []
            return group

    group = {"matcher": "", "hooks": []}
    stop_hooks.append(group)
    return group


def _write_if_changed(path: Path, original: dict, updated: dict) -> bool:
    if updated == original:
        return False
    path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    return True
