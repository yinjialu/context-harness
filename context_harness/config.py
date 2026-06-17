from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_HOME = Path("~/.context-harness").expanduser()


@dataclass(frozen=True)
class SourceConfig:
    enabled: bool
    input_dir: Path
    output_dir: Path

    @property
    def sessions_dir(self) -> Path:
        return self.input_dir

    @property
    def projects_dir(self) -> Path:
        return self.input_dir

@dataclass(frozen=True)
class MemoryConfig:
    profile_file: Path
    global_context_file: Path


@dataclass(frozen=True)
class AppConfig:
    context_home: Path
    codex: SourceConfig
    claude_code: SourceConfig
    hermes_agent: SourceConfig
    memory: MemoryConfig


def resolve_context_home(cli_context_home: str | Path | None = None) -> Path:
    if cli_context_home is not None:
        return Path(cli_context_home).expanduser().resolve()

    env_home = os.environ.get("CONTEXT_HARNESS_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    return DEFAULT_HOME.resolve()


def _resolve_path(context_home: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return context_home / path


def _load_raw_config(context_home: Path) -> dict:
    config_path = context_home / "config.toml"
    if not config_path.exists():
        return {}
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def load_config(context_home: str | Path | None = None) -> AppConfig:
    resolved_home = resolve_context_home(context_home)
    raw = _load_raw_config(resolved_home)

    codex_raw = raw.get("sources", {}).get("codex", {})
    claude_raw = raw.get("sources", {}).get("claude-code", {})
    hermes_raw = raw.get("sources", {}).get("hermes-agent", {})
    memory_raw = raw.get("memory", {})

    codex = SourceConfig(
        enabled=bool(codex_raw.get("enabled", True)),
        input_dir=_resolve_path(resolved_home, codex_raw.get("sessions_dir", "~/.codex/sessions")),
        output_dir=_resolve_path(resolved_home, codex_raw.get("output_dir", "conversations/codex")),
    )
    claude_code = SourceConfig(
        enabled=bool(claude_raw.get("enabled", True)),
        input_dir=_resolve_path(resolved_home, claude_raw.get("projects_dir", "~/.claude/projects")),
        output_dir=_resolve_path(resolved_home, claude_raw.get("output_dir", "conversations/claude-code")),
    )
    hermes_agent = SourceConfig(
        enabled=bool(hermes_raw.get("enabled", True)),
        input_dir=_resolve_path(resolved_home, hermes_raw.get("sessions_dir", "~/.hermes/sessions")),
        output_dir=_resolve_path(resolved_home, hermes_raw.get("output_dir", "conversations/hermes-agent")),
    )
    memory = MemoryConfig(
        profile_file=_resolve_path(resolved_home, memory_raw.get("profile_file", "memory/user_profile.md")),
        global_context_file=_resolve_path(resolved_home, memory_raw.get("global_context_file", "global-claude.md")),
    )

    return AppConfig(
        context_home=resolved_home,
        codex=codex,
        claude_code=claude_code,
        hermes_agent=hermes_agent,
        memory=memory,
    )
