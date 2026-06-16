from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import resolve_context_home


DEFAULT_CONFIG = """[paths]
context_home = "~/.context-harness"

[sources.codex]
enabled = true
sessions_dir = "~/.codex/sessions"
output_dir = "conversations/codex"

[sources.claude-code]
enabled = true
projects_dir = "~/.claude/projects"
output_dir = "conversations/claude-code"

[memory]
profile_file = "memory/user_profile.md"
global_context_file = "global-claude.md"
"""


@dataclass(frozen=True)
class InitResult:
    context_home: Path
    statuses: dict[str, str]


def _write_if_missing(path: Path, content: str, statuses: dict[str, str]) -> None:
    if path.exists():
        statuses[path.name] = "unchanged"
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    statuses[path.name] = "created"


def initialize_context_home(context_home: str | Path | None = None) -> InitResult:
    home = resolve_context_home(context_home)
    statuses: dict[str, str] = {}

    for directory in [
        home / "conversations" / "codex",
        home / "conversations" / "claude-code",
        home / "memory",
        home / "logs",
        home / "state",
        home / "exports",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    _write_if_missing(home / "config.toml", DEFAULT_CONFIG, statuses)
    _write_if_missing(home / "memory" / "MEMORY.md", "# Memory\n", statuses)
    _write_if_missing(home / "memory" / "user_profile.md", "# User Profile\n", statuses)
    _write_if_missing(
        home / "global-claude.md",
        "# Personal Context\n\nSee `memory/` for detailed context.\n",
        statuses,
    )

    return InitResult(context_home=home, statuses=statuses)
