from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .collectors.claude_code import sync_claude_code
from .collectors.codex import sync_codex
from .config import load_config, resolve_context_home
from .hooks.claude_code import install_claude_code_hook
from .hooks.codex import install_codex_hook, install_codex_user_hook
from .init import initialize_context_home
from .models import SyncResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--context-home", help="Override context-harness data home")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize context-harness data home")
    init_parser.add_argument("--install-hooks", action="store_true", help="Print hook installation guidance")

    sync_parser = subparsers.add_parser("sync", help="Sync conversations from a source")
    sync_parser.add_argument("source", choices=["codex", "claude-code"])
    sync_mode = sync_parser.add_mutually_exclusive_group()
    sync_mode.add_argument("--latest", type=int)
    sync_mode.add_argument("--all", action="store_true")
    sync_mode.add_argument("--hook-stdin", action="store_true", help="Read hook JSON from stdin and sync its transcript")

    hooks_parser = subparsers.add_parser("hooks", help="Manage Agent hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command", required=True)
    hooks_install = hooks_subparsers.add_parser("install", help="Install hooks")
    hooks_install.add_argument("source", choices=["codex", "claude-code"])
    hooks_install.add_argument(
        "--scope",
        choices=["user", "project"],
        default="user",
        help="Hook scope; user writes user-level config, project writes config under <project-root>",
    )
    hooks_install.add_argument("--project-root", help="Project root for project-local hooks")
    hooks_install.add_argument("--claude-settings", help="Custom Claude Code settings.json path")

    subparsers.add_parser("dream", help="Review conversations and propose memory updates")

    return parser


def _print_result(result: SyncResult) -> None:
    print(
        f"source={result.source} "
        f"checked={result.checked} "
        f"created={result.created} "
        f"updated={result.updated} "
        f"skipped={result.skipped} "
        f"output_dir={result.output_dir}"
    )


def _disabled_result(source: str, output_dir: Path) -> SyncResult:
    return SyncResult(source, 0, 0, 0, 0, str(output_dir))


def _hook_transcript_path() -> Path | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    return Path(transcript_path).expanduser().resolve()


def _project_scope_requested(args: argparse.Namespace) -> bool:
    return args.scope == "project" or args.project_root is not None


def _project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root or ".").expanduser().resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.command == "init":
        result = initialize_context_home(args.context_home)
        print(f"context home: {result.context_home}")
        for name, status in result.statuses.items():
            print(f"{name}: {status}")
        if args.install_hooks:
            codex_changed = install_codex_user_hook(Path.home() / ".codex", result.context_home)
            claude_changed = install_claude_code_hook(Path.home() / ".claude" / "settings.json", result.context_home)
            print(f"codex hook: {'updated' if codex_changed else 'unchanged'}")
            print("codex hook trust: run /hooks in Codex and approve the context-harness hook if prompted")
            print(f"claude-code hook: {'updated' if claude_changed else 'unchanged'}")
        return 0

    if args.command == "sync":
        config = load_config(args.context_home)
        latest = args.latest
        session_path = _hook_transcript_path() if args.hook_stdin else None
        if args.hook_stdin and session_path is None:
            latest = 1
        if args.source == "codex":
            if config.codex.enabled:
                result = sync_codex(
                    config.codex.sessions_dir,
                    config.codex.output_dir,
                    config.context_home / "state" / "codex-sync-state.json",
                    latest=latest,
                    all_sessions=args.all,
                    session_path=session_path,
                )
            else:
                result = _disabled_result("codex", config.codex.output_dir)
            _print_result(result)
            return 0

        if args.source == "claude-code":
            if config.claude_code.enabled:
                result = sync_claude_code(
                    config.claude_code.projects_dir,
                    config.claude_code.output_dir,
                    config.context_home / "state" / "claude-code-sync-state.json",
                    latest=latest,
                    all_sessions=args.all,
                    session_path=session_path,
                )
            else:
                result = _disabled_result("claude-code", config.claude_code.output_dir)
            _print_result(result)
            return 0

    if args.command == "hooks" and args.hooks_command == "install":
        context_home = resolve_context_home(args.context_home)
        if args.source == "codex":
            if _project_scope_requested(args):
                changed = install_codex_hook(_project_root(args), context_home)
            else:
                changed = install_codex_user_hook(Path.home() / ".codex", context_home)
            print(f"codex hook: {'updated' if changed else 'unchanged'}")
            print("codex hook trust: run /hooks in Codex and approve the context-harness hook if prompted")
            return 0

        if args.source == "claude-code":
            if args.claude_settings:
                settings_path = Path(args.claude_settings).expanduser().resolve()
            elif _project_scope_requested(args):
                settings_path = _project_root(args) / ".claude" / "settings.json"
            else:
                settings_path = Path.home() / ".claude" / "settings.json"
            changed = install_claude_code_hook(settings_path, context_home)
            print(f"claude-code hook: {'updated' if changed else 'unchanged'}")
            return 0

    if args.command == "dream":
        print("profile-dreamer workflow is available through the profile-dreamer skill")
        return 0

    parser.print_help()

    return 0


def entrypoint() -> None:
    raise SystemExit(main())
