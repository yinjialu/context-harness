# context-harness V1 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 `context-harness` V1 的本地文件闭环：初始化数据目录、同步 Codex/Claude Code conversations、安装 hooks，并提供 Agent 可调用的 skills。

**Architecture:** 采用 Python + `uv` 实现一个薄 CLI，核心逻辑放在 `context_harness/` package 中。CLI 负责调度 config、init、collectors、hooks；skills 只作为 Agent-facing workflow，调用 CLI，不复制业务逻辑。用户数据通过 `CONTEXT_HARNESS_HOME` 或 `--context-home` 与 repo 机制层隔离。

**Tech Stack:** Python 3.11+, `uv`, standard library `argparse`/`tomllib`/`json`/`pathlib`, `pytest`.

---

## 文件结构

V1 创建以下文件：

```text
context-harness/
  pyproject.toml
  context_harness/
    __init__.py
    cli.py
    config.py
    init.py
    models.py
    markdown.py
    state.py
    collectors/
      __init__.py
      codex.py
      claude_code.py
    hooks/
      __init__.py
      codex.py
      claude_code.py
  skills/
    init-context/SKILL.md
    sync-conversations/SKILL.md
    profile-dreamer/SKILL.md
  tests/
    test_config.py
    test_init.py
    test_markdown.py
    test_codex_collector.py
    test_claude_code_collector.py
    test_hooks.py
    fixtures/
      codex-session.jsonl
      claude-code-session.jsonl
```

职责边界：

- `config.py`：解析 `CONTEXT_HARNESS_HOME`、`--context-home`、`config.toml`，并提供路径解析。
- `init.py`：创建 `$CONTEXT_HARNESS_HOME` 目录、默认 config、memory/global context 文件。
- `models.py`：定义 `Message`、`Conversation`、`SyncResult` 等纯数据结构。
- `markdown.py`：把 `Conversation` 渲染为稳定 Markdown。
- `state.py`：读写 sync state，支持幂等增量同步。
- `collectors/codex.py`：读取 Codex JSONL，过滤噪声，写入 conversations。
- `collectors/claude_code.py`：读取 Claude Code JSONL，过滤噪声，写入 conversations。
- `hooks/codex.py`：幂等修改 `.codex/config.toml` 和 `.codex/hooks.json`。
- `hooks/claude_code.py`：幂等修改 `~/.claude/settings.json`。
- `cli.py`：把 `init`、`sync`、`hooks install` 命令接到上述模块。
- `skills/*/SKILL.md`：Agent 调用层，描述何时调用 CLI。

## Task 1: Python Package 与 CLI 骨架

**Files:**
- Create: `pyproject.toml`
- Create: `context_harness/__init__.py`
- Create: `context_harness/cli.py`
- Test: `tests/test_cli_smoke.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_cli_smoke.py`：

```python
from context_harness.cli import main


def test_cli_help_returns_zero(capsys):
    code = main(["--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "context-harness" in captured.out
    assert "init" in captured.out
    assert "sync" in captured.out
    assert "hooks" in captured.out
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_cli_smoke.py -v
```

Expected: FAIL，错误包含 `ModuleNotFoundError: No module named 'context_harness'`。

- [ ] **Step 3: 写最小 package 配置**

创建 `pyproject.toml`：

```toml
[project]
name = "context-harness"
version = "0.1.0"
description = "Local-first personal AI context loop for Code Agent conversations"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
context-harness = "context_harness.cli:entrypoint"

[dependency-groups]
dev = [
  "pytest>=8.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

创建 `context_harness/__init__.py`：

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

创建 `context_harness/cli.py`：

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize context-harness data home")

    sync_parser = subparsers.add_parser("sync", help="Sync conversations from a source")
    sync_parser.add_argument("source", choices=["codex", "claude-code"])
    sync_mode = sync_parser.add_mutually_exclusive_group()
    sync_mode.add_argument("--latest", type=int)
    sync_mode.add_argument("--all", action="store_true")

    hooks_parser = subparsers.add_parser("hooks", help="Manage Agent hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command")
    hooks_install = hooks_subparsers.add_parser("install", help="Install hooks")
    hooks_install.add_argument("source", choices=["codex", "claude-code"])

    subparsers.add_parser("dream", help="Review conversations and propose memory updates")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_cli_smoke.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml context_harness/__init__.py context_harness/cli.py tests/test_cli_smoke.py
git commit -m "feat: scaffold context-harness cli"
```

## Task 2: Config 与路径解析

**Files:**
- Create: `context_harness/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_config.py`：

```python
from pathlib import Path

from context_harness.config import load_config, resolve_context_home


def test_resolve_context_home_prefers_cli_path(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_HARNESS_HOME", str(tmp_path / "env-home"))

    home = resolve_context_home(cli_context_home=tmp_path / "cli-home")

    assert home == (tmp_path / "cli-home").resolve()


def test_resolve_context_home_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_HARNESS_HOME", str(tmp_path / "env-home"))

    home = resolve_context_home()

    assert home == (tmp_path / "env-home").resolve()


def test_load_config_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTEXT_HARNESS_HOME", raising=False)

    config = load_config(context_home=tmp_path)

    assert config.context_home == tmp_path.resolve()
    assert config.codex.sessions_dir == Path("~/.codex/sessions").expanduser()
    assert config.codex.output_dir == tmp_path / "conversations" / "codex"
    assert config.claude_code.projects_dir == Path("~/.claude/projects").expanduser()
    assert config.claude_code.output_dir == tmp_path / "conversations" / "claude-code"
    assert config.memory.global_context_file == tmp_path / "global-claude.md"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL，错误包含 `ModuleNotFoundError` 或 `cannot import name 'load_config'`。

- [ ] **Step 3: 实现 config 模块**

创建 `context_harness/config.py`：

```python
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
    memory_raw = raw.get("memory", {})

    codex = SourceConfig(
        enabled=bool(codex_raw.get("enabled", True)),
        input_dir=Path(codex_raw.get("sessions_dir", "~/.codex/sessions")).expanduser(),
        output_dir=_resolve_path(resolved_home, codex_raw.get("output_dir", "conversations/codex")),
    )
    claude_code = SourceConfig(
        enabled=bool(claude_raw.get("enabled", True)),
        input_dir=Path(claude_raw.get("projects_dir", "~/.claude/projects")).expanduser(),
        output_dir=_resolve_path(resolved_home, claude_raw.get("output_dir", "conversations/claude-code")),
    )
    memory = MemoryConfig(
        profile_file=_resolve_path(resolved_home, memory_raw.get("profile_file", "memory/user_profile.md")),
        global_context_file=_resolve_path(resolved_home, memory_raw.get("global_context_file", "global-claude.md")),
    )

    return AppConfig(
        context_home=resolved_home,
        codex=codex,
        claude_code=claude_code,
        memory=memory,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add context_harness/config.py tests/test_config.py
git commit -m "feat: add context home config"
```

## Task 3: 数据目录初始化

**Files:**
- Create: `context_harness/init.py`
- Modify: `context_harness/cli.py`
- Test: `tests/test_init.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_init.py`：

```python
from context_harness.init import initialize_context_home


def test_initialize_context_home_creates_expected_files(tmp_path):
    result = initialize_context_home(tmp_path)

    assert result.context_home == tmp_path.resolve()
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "conversations" / "codex").is_dir()
    assert (tmp_path / "conversations" / "claude-code").is_dir()
    assert (tmp_path / "memory" / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "user_profile.md").exists()
    assert (tmp_path / "global-claude.md").exists()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "state").is_dir()
    assert "created" in result.statuses


def test_initialize_context_home_is_idempotent(tmp_path):
    initialize_context_home(tmp_path)
    second = initialize_context_home(tmp_path)

    assert second.statuses["config.toml"] == "unchanged"
    assert second.statuses["global-claude.md"] == "unchanged"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_init.py -v
```

Expected: FAIL，错误包含 `No module named 'context_harness.init'`。

- [ ] **Step 3: 实现 init 模块**

创建 `context_harness/init.py`：

```python
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
```

- [ ] **Step 4: 接入 CLI init**

修改 `context_harness/cli.py`：

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence

from .init import initialize_context_home


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    parser.add_argument("--context-home", help="Override CONTEXT_HARNESS_HOME")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize context-harness data home")
    init_parser.add_argument("--install-hooks", action="store_true")

    sync_parser = subparsers.add_parser("sync", help="Sync conversations from a source")
    sync_parser.add_argument("source", choices=["codex", "claude-code"])
    sync_mode = sync_parser.add_mutually_exclusive_group()
    sync_mode.add_argument("--latest", type=int)
    sync_mode.add_argument("--all", action="store_true")

    hooks_parser = subparsers.add_parser("hooks", help="Manage Agent hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command")
    hooks_install = hooks_subparsers.add_parser("install", help="Install hooks")
    hooks_install.add_argument("source", choices=["codex", "claude-code"])

    subparsers.add_parser("dream", help="Review conversations and propose memory updates")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.command == "init":
        result = initialize_context_home(args.context_home)
        print(f"context home: {result.context_home}")
        for name, status in sorted(result.statuses.items()):
            print(f"{name}: {status}")
        if args.install_hooks:
            print("hook installation is available through `context-harness hooks install`")
        return 0

    return 0


def entrypoint() -> None:
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_init.py tests/test_cli_smoke.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add context_harness/init.py context_harness/cli.py tests/test_init.py
git commit -m "feat: initialize context home"
```

## Task 4: Conversation 数据模型与 Markdown 渲染

**Files:**
- Create: `context_harness/models.py`
- Create: `context_harness/markdown.py`
- Test: `tests/test_markdown.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_markdown.py`：

```python
from datetime import datetime, timezone

from context_harness.markdown import render_conversation
from context_harness.models import Conversation, Message


def test_render_conversation_markdown():
    conversation = Conversation(
        source="codex",
        session_id="session-123",
        title="Build context harness",
        created_at=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
        synced_at=datetime(2026, 6, 16, 8, 30, tzinfo=timezone.utc),
        messages=[
            Message(role="user", content="继续", created_at=datetime(2026, 6, 16, 8, 1, tzinfo=timezone.utc)),
            Message(role="assistant", content="好的。", created_at=datetime(2026, 6, 16, 8, 2, tzinfo=timezone.utc)),
        ],
        metadata={"Project": "/tmp/project"},
    )

    rendered = render_conversation(conversation)

    assert rendered.startswith("# 2026-06-16 - Build context harness")
    assert "- **Source**: codex" in rendered
    assert "- **Session**: `session-123`" in rendered
    assert "- **Messages**: 2" in rendered
    assert "- **Project**: /tmp/project" in rendered
    assert "### **User** 08:01" in rendered
    assert "### **Assistant** 08:02" in rendered
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_markdown.py -v
```

Expected: FAIL，错误包含 `No module named 'context_harness.markdown'`。

- [ ] **Step 3: 实现模型与渲染**

创建 `context_harness/models.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class Conversation:
    source: str
    session_id: str
    title: str
    created_at: datetime
    synced_at: datetime
    messages: list[Message]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncResult:
    source: str
    checked: int
    created: int
    updated: int
    skipped: int
    output_dir: str
```

创建 `context_harness/markdown.py`：

```python
from __future__ import annotations

from datetime import datetime

from .models import Conversation, Message


def _date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _time(value: datetime | None) -> str:
    if value is None:
        return ""
    return " " + value.strftime("%H:%M")


def _role_label(role: str) -> str:
    if role == "user":
        return "User"
    if role == "assistant":
        return "Assistant"
    return role.title()


def _render_message(message: Message) -> str:
    label = _role_label(message.role)
    return f"### **{label}**{_time(message.created_at)}\n{message.content.strip()}\n"


def render_conversation(conversation: Conversation) -> str:
    lines = [
        f"# {_date(conversation.created_at)} - {conversation.title}",
        f"- **Source**: {conversation.source}",
        f"- **Session**: `{conversation.session_id}`",
        f"- **Messages**: {len(conversation.messages)}",
        f"- **Synced At**: {conversation.synced_at.isoformat()}",
    ]
    for key, value in conversation.metadata.items():
        lines.append(f"- **{key}**: {value}")
    lines.append("---")
    lines.append("")
    lines.extend(_render_message(message) for message in conversation.messages)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_markdown.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add context_harness/models.py context_harness/markdown.py tests/test_markdown.py
git commit -m "feat: render conversation archives"
```

## Task 5: Codex Collector

**Files:**
- Create: `context_harness/collectors/__init__.py`
- Create: `context_harness/collectors/codex.py`
- Create: `context_harness/state.py`
- Create: `tests/fixtures/codex-session.jsonl`
- Test: `tests/test_codex_collector.py`

- [ ] **Step 1: 写 fixture**

创建 `tests/fixtures/codex-session.jsonl`：

```jsonl
{"timestamp":"2026-06-16T08:00:00Z","type":"session_meta","payload":{"id":"codex-session-1","cwd":"/tmp/project","title":"Context Harness"}}
{"timestamp":"2026-06-16T08:01:00Z","type":"event_msg","payload":{"role":"user","content":"继续"}}
{"timestamp":"2026-06-16T08:02:00Z","type":"event_msg","payload":{"role":"assistant","content":"好的，继续。"}}
{"timestamp":"2026-06-16T08:03:00Z","type":"tool_call","payload":{"name":"exec_command"}}
```

- [ ] **Step 2: 写失败测试**

创建 `tests/test_codex_collector.py`：

```python
from pathlib import Path

from context_harness.collectors.codex import sync_codex


def test_sync_codex_writes_markdown_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    result = sync_codex(sessions_dir, output_dir, state_path, latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert result.skipped == 0
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: codex" in content
    assert "- **Messages**: 2" in content
    assert "### **User** 08:01" in content
    assert "### **Assistant** 08:02" in content
    assert "tool_call" not in content


def test_sync_codex_skips_unchanged_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    sync_codex(sessions_dir, output_dir, state_path, latest=1)
    second = sync_codex(sessions_dir, output_dir, state_path, latest=1)

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_sync_codex_missing_source_dir_returns_empty_result(tmp_path):
    result = sync_codex(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_codex_collector.py -v
```

Expected: FAIL，错误包含 `No module named 'context_harness.collectors'`。

- [ ] **Step 4: 实现 state 与 Codex collector**

创建 `context_harness/collectors/__init__.py`：

```python
__all__ = []
```

创建 `context_harness/state.py`：

```python
from __future__ import annotations

import json
from pathlib import Path


def read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
```

创建 `context_harness/collectors/codex.py`：

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..markdown import render_conversation
from ..models import Conversation, Message, SyncResult
from ..state import read_state, write_state


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-")


def _read_codex_session(path: Path) -> Conversation | None:
    session_id = path.stem
    title = path.stem
    created_at: datetime | None = None
    metadata: dict[str, str] = {}
    messages: list[Message] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        timestamp = _parse_time(event.get("timestamp"))
        event_type = event.get("type")
        payload = event.get("payload", {})
        if created_at is None:
            created_at = timestamp
        if event_type == "session_meta":
            session_id = payload.get("id", session_id)
            title = payload.get("title", title)
            if payload.get("cwd"):
                metadata["Project"] = payload["cwd"]
        if event_type == "event_msg" and payload.get("role") in {"user", "assistant"}:
            content = payload.get("content", "")
            if content.strip():
                messages.append(Message(role=payload["role"], content=content, created_at=timestamp))

    if not messages:
        return None
    return Conversation(
        source="codex",
        session_id=session_id,
        title=title,
        created_at=created_at or datetime.now(timezone.utc),
        synced_at=datetime.now(timezone.utc),
        messages=messages,
        metadata=metadata,
    )


def sync_codex(sessions_dir: Path, output_dir: Path, state_path: Path, latest: int | None = None, all_sessions: bool = False) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not sessions_dir.exists():
        return SyncResult("codex", 0, 0, 0, 0, str(output_dir))
    state = read_state(state_path)
    files = sorted(sessions_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if latest is not None and not all_sessions:
        files = files[:latest]

    created = updated = skipped = checked = 0
    for path in files:
        checked += 1
        conversation = _read_codex_session(path)
        if conversation is None:
            skipped += 1
            continue
        key = conversation.session_id
        count = len(conversation.messages)
        target = output_dir / f"{conversation.created_at.strftime('%Y%m%d')}_{_safe_name(key)[:8]}.md"
        previous = state.get(key)
        if previous and previous.get("messages") == count and target.exists():
            skipped += 1
            continue
        if target.exists():
            updated += 1
        else:
            created += 1
        target.write_text(render_conversation(conversation), encoding="utf-8")
        state[key] = {"messages": count, "path": str(target)}

    write_state(state_path, state)
    return SyncResult("codex", checked, created, updated, skipped, str(output_dir))
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_codex_collector.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add context_harness/collectors context_harness/state.py tests/fixtures/codex-session.jsonl tests/test_codex_collector.py
git commit -m "feat: sync codex conversations"
```

## Task 6: Claude Code Collector

**Files:**
- Create: `context_harness/collectors/claude_code.py`
- Create: `tests/fixtures/claude-code-session.jsonl`
- Test: `tests/test_claude_code_collector.py`

- [ ] **Step 1: 写 fixture**

创建 `tests/fixtures/claude-code-session.jsonl`：

```jsonl
{"sessionId":"claude-session-1","timestamp":"2026-06-16T08:00:00Z","type":"summary","summary":"Context Harness"}
{"sessionId":"claude-session-1","timestamp":"2026-06-16T08:01:00Z","type":"user","message":{"role":"user","content":"继续"}}
{"sessionId":"claude-session-1","timestamp":"2026-06-16T08:02:00Z","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"好的，继续。"}]}}
{"sessionId":"claude-session-1","timestamp":"2026-06-16T08:03:00Z","type":"tool_result","content":"noise"}
```

- [ ] **Step 2: 写失败测试**

创建 `tests/test_claude_code_collector.py`：

```python
from pathlib import Path

from context_harness.collectors.claude_code import sync_claude_code


def test_sync_claude_code_writes_markdown_archive(tmp_path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "-tmp-project"
    project_dir.mkdir(parents=True)
    fixture = Path("tests/fixtures/claude-code-session.jsonl").read_text(encoding="utf-8")
    (project_dir / "claude-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    result = sync_claude_code(projects_dir, output_dir, state_path, latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: claude-code" in content
    assert "- **Messages**: 2" in content
    assert "### **User** 08:01" in content
    assert "### **Assistant** 08:02" in content
    assert "tool_result" not in content


def test_sync_claude_code_missing_source_dir_returns_empty_result(tmp_path):
    result = sync_claude_code(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_claude_code_collector.py -v
```

Expected: FAIL，错误包含 `No module named 'context_harness.collectors.claude_code'`。

- [ ] **Step 4: 实现 Claude Code collector**

创建 `context_harness/collectors/claude_code.py`：

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..markdown import render_conversation
from ..models import Conversation, Message, SyncResult
from ..state import read_state, write_state


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-")


def _message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if item.get("type") == "text").strip()
    return ""


def _read_session(path: Path) -> Conversation | None:
    session_id = path.stem
    title = path.stem
    created_at: datetime | None = None
    messages: list[Message] = []
    metadata = {"Project": path.parent.name}

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        timestamp = _parse_time(event.get("timestamp"))
        created_at = created_at or timestamp
        session_id = event.get("sessionId", session_id)
        if event.get("type") == "summary" and event.get("summary"):
            title = event["summary"]
        if event.get("type") in {"user", "assistant"}:
            message = event.get("message", {})
            role = message.get("role") or event.get("type")
            if role not in {"user", "assistant"}:
                continue
            content = _message_text(message)
            if content:
                messages.append(Message(role=role, content=content, created_at=timestamp))

    if not messages:
        return None
    return Conversation(
        source="claude-code",
        session_id=session_id,
        title=title,
        created_at=created_at or datetime.now(timezone.utc),
        synced_at=datetime.now(timezone.utc),
        messages=messages,
        metadata=metadata,
    )


def sync_claude_code(projects_dir: Path, output_dir: Path, state_path: Path, latest: int | None = None, all_sessions: bool = False) -> SyncResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not projects_dir.exists():
        return SyncResult("claude-code", 0, 0, 0, 0, str(output_dir))
    state = read_state(state_path)
    files = sorted(projects_dir.glob("*/*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if latest is not None and not all_sessions:
        files = files[:latest]

    created = updated = skipped = checked = 0
    for path in files:
        checked += 1
        conversation = _read_session(path)
        if conversation is None:
            skipped += 1
            continue
        key = conversation.session_id
        count = len(conversation.messages)
        target = output_dir / f"{conversation.created_at.strftime('%Y%m%d')}_{_safe_name(key)[:8]}.md"
        previous = state.get(key)
        if previous and previous.get("messages") == count and target.exists():
            skipped += 1
            continue
        if target.exists():
            updated += 1
        else:
            created += 1
        target.write_text(render_conversation(conversation), encoding="utf-8")
        state[key] = {"messages": count, "path": str(target)}

    write_state(state_path, state)
    return SyncResult("claude-code", checked, created, updated, skipped, str(output_dir))
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_claude_code_collector.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add context_harness/collectors/claude_code.py tests/fixtures/claude-code-session.jsonl tests/test_claude_code_collector.py
git commit -m "feat: sync claude code conversations"
```

## Task 7: Hook Installers

**Files:**
- Create: `context_harness/hooks/__init__.py`
- Create: `context_harness/hooks/codex.py`
- Create: `context_harness/hooks/claude_code.py`
- Test: `tests/test_hooks.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_hooks.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_hooks.py -v
```

Expected: FAIL，错误包含 `No module named 'context_harness.hooks'`。

- [ ] **Step 3: 实现 hook installers**

创建 `context_harness/hooks/__init__.py`：

```python
__all__ = []
```

创建 `context_harness/hooks/codex.py`：

```python
from __future__ import annotations

import json
import shlex
from pathlib import Path


def _command(context_home: Path) -> str:
    return f"context-harness --context-home {shlex.quote(str(context_home))} sync codex --latest 1 >/tmp/context-harness-codex.log 2>&1 || true"


def _ensure_config(config_path: Path) -> bool:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text("[features]\ncodex_hooks = true\n", encoding="utf-8")
        return True
    content = config_path.read_text(encoding="utf-8")
    if "codex_hooks = true" in content:
        return False
    if "[features]" in content:
        content = content.replace("[features]", "[features]\ncodex_hooks = true", 1)
    else:
        content = content.rstrip() + "\n\n[features]\ncodex_hooks = true\n"
    config_path.write_text(content, encoding="utf-8")
    return True


def _ensure_hooks(hooks_path: Path, context_home: Path) -> bool:
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    hooks = payload.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    command = _command(context_home)
    for group in stop:
        for hook in group.get("hooks", []):
            if hook.get("type") == "command" and "sync codex --latest 1" in hook.get("command", ""):
                if hook.get("command") == command:
                    return False
                hook["command"] = command
                hooks_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return True
    stop.append({"hooks": [{"type": "command", "command": command, "timeout": 30, "statusMessage": "Syncing context-harness Codex archive"}]})
    hooks_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def install_codex_hook(project_root: Path, context_home: Path) -> bool:
    config_changed = _ensure_config(project_root / ".codex" / "config.toml")
    hooks_changed = _ensure_hooks(project_root / ".codex" / "hooks.json", context_home)
    return config_changed or hooks_changed
```

创建 `context_harness/hooks/claude_code.py`：

```python
from __future__ import annotations

import json
import shlex
from pathlib import Path


def _command(context_home: Path) -> str:
    return f"context-harness --context-home {shlex.quote(str(context_home))} sync claude-code --latest 1 >/tmp/context-harness-claude-code.log 2>&1 || true"


def install_claude_code_hook(settings_path: Path, context_home: Path) -> bool:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    command = _command(context_home)
    for group in stop:
        for hook in group.get("hooks", []):
            if hook.get("type") == "command" and "sync claude-code --latest 1" in hook.get("command", ""):
                if hook.get("command") == command:
                    return False
                hook["command"] = command
                settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return True
    stop.append({"hooks": [{"type": "command", "command": command, "timeout": 30, "async": True}]})
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_hooks.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add context_harness/hooks tests/test_hooks.py
git commit -m "feat: install agent sync hooks"
```

## Task 8: CLI 接入 sync 与 hooks

**Files:**
- Modify: `context_harness/cli.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_cli_commands.py`：

```python
from pathlib import Path

from context_harness.cli import main


def test_cli_sync_codex(tmp_path, capsys):
    context_home = tmp_path / "home"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")
    context_home.mkdir()
    (context_home / "config.toml").write_text(
        f"""[sources.codex]
enabled = true
sessions_dir = "{sessions}"
output_dir = "conversations/codex"
""",
        encoding="utf-8",
    )

    code = main(["--context-home", str(context_home), "sync", "codex", "--latest", "1"])

    captured = capsys.readouterr()
    assert code == 0
    assert "created=1" in captured.out
    assert list((context_home / "conversations" / "codex").glob("*.md"))
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_cli_commands.py -v
```

Expected: FAIL，因为 `sync` 命令尚未调 collector。

- [ ] **Step 3: 修改 CLI**

用以下内容替换 `context_harness/cli.py`：

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .collectors.claude_code import sync_claude_code
from .collectors.codex import sync_codex
from .config import load_config
from .hooks.claude_code import install_claude_code_hook
from .hooks.codex import install_codex_hook
from .init import initialize_context_home


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    parser.add_argument("--context-home", help="Override CONTEXT_HARNESS_HOME")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize context-harness data home")
    init_parser.add_argument("--install-hooks", action="store_true")

    sync_parser = subparsers.add_parser("sync", help="Sync conversations from a source")
    sync_parser.add_argument("source", choices=["codex", "claude-code"])
    sync_mode = sync_parser.add_mutually_exclusive_group()
    sync_mode.add_argument("--latest", type=int)
    sync_mode.add_argument("--all", action="store_true")

    hooks_parser = subparsers.add_parser("hooks", help="Manage Agent hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command")
    hooks_install = hooks_subparsers.add_parser("install", help="Install hooks")
    hooks_install.add_argument("source", choices=["codex", "claude-code"])
    hooks_install.add_argument("--project-root", default=".")
    hooks_install.add_argument("--claude-settings")

    subparsers.add_parser("dream", help="Review conversations and propose memory updates")

    return parser


def _print_result(result) -> None:
    print(
        f"source={result.source} checked={result.checked} "
        f"created={result.created} updated={result.updated} skipped={result.skipped} "
        f"output_dir={result.output_dir}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.command == "init":
        result = initialize_context_home(args.context_home)
        print(f"context home: {result.context_home}")
        for name, status in sorted(result.statuses.items()):
            print(f"{name}: {status}")
        if args.install_hooks:
            config = load_config(result.context_home)
            codex_changed = install_codex_hook(Path.cwd(), config.context_home)
            claude_changed = install_claude_code_hook(Path.home() / ".claude" / "settings.json", config.context_home)
            print(f"codex hook: {'updated' if codex_changed else 'unchanged'}")
            print(f"claude-code hook: {'updated' if claude_changed else 'unchanged'}")
        return 0

    if args.command == "sync":
        config = load_config(args.context_home)
        latest = args.latest if not args.all else None
        if args.source == "codex":
            result = sync_codex(config.codex.sessions_dir, config.codex.output_dir, config.context_home / "state" / "codex-sync-state.json", latest=latest, all_sessions=args.all)
        else:
            result = sync_claude_code(config.claude_code.projects_dir, config.claude_code.output_dir, config.context_home / "state" / "claude-code-sync-state.json", latest=latest, all_sessions=args.all)
        _print_result(result)
        return 0

    if args.command == "hooks" and args.hooks_command == "install":
        config = load_config(args.context_home)
        if args.source == "codex":
            changed = install_codex_hook(Path(args.project_root).resolve(), config.context_home)
        else:
            settings_path = Path(args.claude_settings).expanduser() if args.claude_settings else Path.home() / ".claude" / "settings.json"
            changed = install_claude_code_hook(settings_path, config.context_home)
        print("updated" if changed else "unchanged")
        return 0

    if args.command == "dream":
        print("profile-dreamer workflow is available through the profile-dreamer skill")
        return 0

    parser.print_help()
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_cli_commands.py tests/test_cli_smoke.py -v
```

Expected: PASS。

- [ ] **Step 5: 运行全量测试**

Run:

```bash
uv run pytest -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add context_harness/cli.py tests/test_cli_commands.py
git commit -m "feat: wire cli sync and hooks"
```

## Task 9: Skills

**Files:**
- Create: `skills/init-context/SKILL.md`
- Create: `skills/sync-conversations/SKILL.md`
- Create: `skills/profile-dreamer/SKILL.md`

- [ ] **Step 1: 创建 `init-context` skill**

创建 `skills/init-context/SKILL.md`：

```markdown
---
name: init-context
description: Initialize a context-harness personal context home, data directories, global context files, and optional Codex/Claude Code hooks. Use when the user asks to initialize context-harness, set up a personal context system, configure automatic Code Agent conversation backup, or repair context-harness hooks.
---

# Init Context

Use this skill to initialize or repair a `context-harness` installation.

## Workflow

1. Locate the `context-harness` repository or ask the user for the path.
2. Choose the data home:
   - Use `CONTEXT_HARNESS_HOME` when set.
   - Use the user's explicit path when provided.
   - Otherwise use `~/.context-harness`.
3. Run:

```bash
uv run context-harness --context-home <context-home> init
```

4. If the user wants automatic backup hooks, run:

```bash
uv run context-harness --context-home <context-home> hooks install codex
uv run context-harness --context-home <context-home> hooks install claude-code
```

5. Report the data home and hook status.

Do not store user conversations or memory inside the `context-harness` repository unless the user explicitly chooses that path as the data home.
```

- [ ] **Step 2: 创建 `sync-conversations` skill**

创建 `skills/sync-conversations/SKILL.md`：

```markdown
---
name: sync-conversations
description: Sync local Codex and Claude Code conversation records into a context-harness data home. Use when the user asks to back up Code Agent conversations, sync Codex sessions, sync Claude Code sessions, run full or incremental conversation backup, or inspect context-harness sync status.
---

# Sync Conversations

Use this skill to collect local Code Agent conversations into `context-harness`.

## Sources

V1 supports:

- `codex`
- `claude-code`

Claude Web, Antigravity, ChatGPT, Gemini, and browser exports are outside V1.

## Commands

Incremental sync:

```bash
uv run context-harness --context-home <context-home> sync codex --latest 1
uv run context-harness --context-home <context-home> sync claude-code --latest 1
```

Full sync:

```bash
uv run context-harness --context-home <context-home> sync codex --all
uv run context-harness --context-home <context-home> sync claude-code --all
```

After running, summarize `checked`, `created`, `updated`, `skipped`, and `output_dir`.
```

- [ ] **Step 3: 创建 `profile-dreamer` skill**

创建 `skills/profile-dreamer/SKILL.md`：

```markdown
---
name: profile-dreamer
description: Review context-harness conversation archives and propose durable memory/profile updates. Use when the user asks to dream, update memory, refresh their profile, extract personal context from conversations, or maintain the context-harness memory loop.
---

# Profile Dreamer

Use this skill to review archived conversations and propose memory/profile updates.

## Workflow

1. Resolve the context home from `CONTEXT_HARNESS_HOME`, the user's explicit path, or `~/.context-harness`.
2. Read:
   - `state/dream-state.json`
   - `global-claude.md`
   - `memory/user_profile.md`
   - new or changed files under `conversations/`
3. Extract durable signals:
   - identity changes
   - technical preferences
   - recurring working style
   - active projects
   - writing/content direction
   - explicit instructions for AI agents
4. Present a reviewable proposal grouped by add/update/strengthen/deprecate.
5. Wait for user confirmation before writing memory files.
6. After confirmation, update:
   - `global-claude.md`
   - `memory/user_profile.md`
   - `logs/dream.md`
   - `state/dream-state.json`

Do not silently rewrite memory/profile files.
```

- [ ] **Step 4: 验证 skill frontmatter**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
for path in Path("skills").glob("*/SKILL.md"):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    assert "\nname:" in text, path
    assert "\ndescription:" in text, path
print("skills ok")
PY
```

Expected: 输出 `skills ok`。

- [ ] **Step 5: 提交**

```bash
git add skills
git commit -m "feat: add context harness skills"
```

## Task 10: README 快速开始与最终验证

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README**

用以下内容替换 `README.md`：

```markdown
# context-harness

`context-harness` 是一个 local-first 的个人 AI 上下文闭环框架。

V1 聚焦两个本地 Code Agent 数据源：

- Codex
- Claude Code

项目采用“机制层”和“用户数据层”分离的设计。仓库只维护 CLI、skills、hook installers、templates、docs 和 tests；conversations、memory、logs、sync state 等用户数据放在可配置的数据目录中，例如 `~/.context-harness`。

## 快速开始

安装依赖：

```bash
uv sync
```

初始化数据目录：

```bash
uv run context-harness --context-home ~/.context-harness init
```

同步最近一条 Codex conversation：

```bash
uv run context-harness --context-home ~/.context-harness sync codex --latest 1
```

同步最近一条 Claude Code conversation：

```bash
uv run context-harness --context-home ~/.context-harness sync claude-code --latest 1
```

安装自动同步 hooks：

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

## 数据目录

默认数据目录是 `~/.context-harness`，也可以通过 `CONTEXT_HARNESS_HOME` 或 `--context-home` 指定。

```text
$CONTEXT_HARNESS_HOME/
  config.toml
  conversations/
    codex/
    claude-code/
  memory/
    MEMORY.md
    user_profile.md
  logs/
  state/
```

## 设计文档

- [docs/superpowers/specs/2026-06-16-context-harness-design.md](docs/superpowers/specs/2026-06-16-context-harness-design.md)
- [docs/superpowers/plans/2026-06-16-context-harness-v1-core.md](docs/superpowers/plans/2026-06-16-context-harness-v1-core.md)
```

- [ ] **Step 2: 运行全量测试**

Run:

```bash
uv run pytest -v
```

Expected: PASS。

- [ ] **Step 3: CLI smoke test**

Run:

```bash
uv run context-harness --help
uv run context-harness --context-home /tmp/context-harness-smoke init
uv run context-harness --context-home /tmp/context-harness-smoke sync codex --latest 1
```

Expected:

- `--help` 输出包含 `init`、`sync`、`hooks`
- `init` 输出 `context home: /tmp/context-harness-smoke`
- `sync codex` 在没有真实 Codex sessions 时不崩溃，并输出 `checked=0`

- [ ] **Step 4: 提交**

```bash
git add README.md context_harness tests skills
git commit -m "docs: add quick start"
```

## 自检

Spec 覆盖：

- 独立项目：已在 `/Users/jialu/Documents/context-harness` 初始化。
- V1 source scope：Task 5/6 只实现 `codex` 和 `claude-code`。
- 数据隔离：Task 2/3 使用 `CONTEXT_HARNESS_HOME` 和 `--context-home`。
- CLI：Task 1/3/8 实现 `init`、`sync`、`hooks`、`dream` 占位入口。
- Hooks：Task 7/8 实现 Codex 和 Claude Code hook installation。
- Skills：Task 9 实现 `init-context`、`sync-conversations`、`profile-dreamer`。
- Tests：每个核心模块都有 synthetic fixture 或单元测试。

执行注意：

- 如果实际 Codex JSONL 或 Claude Code JSONL schema 与 fixture 不一致，先补一个真实样本的脱敏 fixture，再调整 collector parser。
- Missing source directory 已在 Task 5 和 Task 6 作为正式测试覆盖。
