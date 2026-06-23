from __future__ import annotations

import json
import re
import shlex
import shutil
from pathlib import Path


_SYNC_MARKERS = ("sync codex", "extract_codex.py")
_FEATURES_SECTION_RE = re.compile(r"^\s*\[\s*features\s*\]\s*(?:#.*)?$")
_SECTION_RE = re.compile(r"^\s*\[.*\]\s*(?:#.*)?$")


def install_codex_hook(project_root: Path, context_home: Path) -> bool:
    return _install_codex_hook_dir(project_root / ".codex", context_home)


def install_codex_user_hook(codex_home: Path, context_home: Path) -> bool:
    return _install_codex_hook_dir(codex_home, context_home)


def _install_codex_hook_dir(codex_dir: Path, context_home: Path) -> bool:
    config_path = codex_dir / "config.toml"
    hooks_path = codex_dir / "hooks.json"
    command = (
        f"cd {shlex.quote(str(_harness_root()))} && "
        f"{shlex.quote(_uv_executable())} run --with . "
        f"python -m context_harness --context-home {shlex.quote(str(context_home))} "
        "sync codex --hook-stdin >/tmp/context-harness-codex.log 2>&1 || true"
    )

    codex_dir.mkdir(parents=True, exist_ok=True)

    changed = _ensure_codex_hooks_feature(config_path)
    changed = _ensure_stop_command_hook(hooks_path, command) or changed
    return changed


def _harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _uv_executable() -> str:
    uv_path = shutil.which("uv")
    if uv_path is None:
        raise RuntimeError("uv executable not found; install uv before installing context-harness hooks")
    return uv_path


def _ensure_codex_hooks_feature(config_path: Path) -> bool:
    if config_path.exists():
        original = config_path.read_text(encoding="utf-8")
    else:
        original = ""

    updated = _set_feature_flag(original, "hooks", "true")
    if _has_feature_flag(updated, "codex_hooks"):
        updated = _set_feature_flag(updated, "codex_hooks", "true")
    if updated == original:
        return False

    config_path.write_text(updated, encoding="utf-8")
    return True


def _set_feature_flag(content: str, key: str, value: str) -> str:
    lines = content.splitlines()
    has_trailing_newline = content.endswith("\n")
    features_start: int | None = None
    features_end = len(lines)

    for index, line in enumerate(lines):
        stripped = line.strip()
        if _FEATURES_SECTION_RE.match(line):
            features_start = index
            continue
        if features_start is not None and index > features_start and _SECTION_RE.match(stripped):
            features_end = index
            break

    if features_start is None:
        if lines:
            lines.extend(["", "[features]", f"{key} = {value}"])
        else:
            lines.extend(["[features]", f"{key} = {value}"])
        return "\n".join(lines) + "\n"

    key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index in range(features_start + 1, features_end):
        if key_pattern.match(lines[index]):
            if lines[index] == f"{key} = {value}":
                return content if has_trailing_newline else content + "\n"
            lines[index] = f"{key} = {value}"
            return "\n".join(lines) + "\n"

    lines.insert(features_end, f"{key} = {value}")
    return "\n".join(lines) + "\n"


def _has_feature_flag(content: str, key: str) -> bool:
    lines = content.splitlines()
    features_start: int | None = None
    features_end = len(lines)
    key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")

    for index, line in enumerate(lines):
        stripped = line.strip()
        if _FEATURES_SECTION_RE.match(line):
            features_start = index
            continue
        if features_start is not None and index > features_start and _SECTION_RE.match(stripped):
            features_end = index
            break

    if features_start is None:
        return False

    return any(key_pattern.match(lines[index]) for index in range(features_start + 1, features_end))


def _ensure_stop_command_hook(hooks_path: Path, command: str) -> bool:
    original = _load_json_object(hooks_path)
    updated = json.loads(json.dumps(original))

    hooks = updated.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])
    if not isinstance(stop_hooks, list):
        stop_hooks = []
        hooks["Stop"] = stop_hooks

    if _update_existing_command(stop_hooks, command):
        return _write_if_changed(hooks_path, original, updated)

    target_group = _first_hook_group(stop_hooks)
    target_group.setdefault("hooks", []).append(_command_hook(command))
    return _write_if_changed(hooks_path, original, updated)


def _load_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _command_hook(command: str) -> dict:
    return {
        "type": "command",
        "command": command,
        "timeout": 30,
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
            if isinstance(existing_command, str) and _is_sync_command(existing_command):
                if not found:
                    hook.update(_command_hook(command))
                    hook.pop("async", None)
                    retained_hooks.append(hook)
                    found = True
                continue
            retained_hooks.append(hook)
        group["hooks"] = retained_hooks
    return found


def _is_sync_command(command: str) -> bool:
    return any(marker in command for marker in _SYNC_MARKERS)


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
