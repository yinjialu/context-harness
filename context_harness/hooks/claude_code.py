from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path


_SYNC_MARKER = "sync claude-code"


def install_claude_code_hook(settings_path: Path, context_home: Path) -> bool:
    command = (
        f"cd {shlex.quote(str(_harness_root()))} && "
        f"{shlex.quote(_uv_executable())} run --with . "
        f"python -m context_harness --context-home {shlex.quote(str(context_home))} "
        "sync claude-code --hook-stdin >/tmp/context-harness-claude-code.log 2>&1 || true"
    )

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    return _ensure_stop_command_hook(settings_path, command)


def _harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _uv_executable() -> str:
    uv_path = shutil.which("uv")
    if uv_path is None:
        raise RuntimeError("uv executable not found; install uv before installing context-harness hooks")
    return uv_path


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
        hooks = group.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        retained_hooks = []
        for hook in hooks:
            if not isinstance(hook, dict):
                retained_hooks.append(hook)
                continue
            existing_command = hook.get("command")
            if isinstance(existing_command, str) and _SYNC_MARKER in existing_command:
                if not found:
                    hook.update(_command_hook(command))
                    retained_hooks.append(hook)
                    found = True
                continue
            retained_hooks.append(hook)
        group["hooks"] = retained_hooks
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
