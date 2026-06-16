from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .collectors.claude_code import sync_claude_code
from .collectors.codex import sync_codex
from .config import load_config, resolve_context_home
from .hooks.claude_code import install_claude_code_hook
from .hooks.codex import install_codex_hook
from .init import initialize_context_home
from .models import SyncResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    parser.add_argument("--context-home", help="Override context-harness data home")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize context-harness data home")
    init_parser.add_argument("--install-hooks", action="store_true", help="Print hook installation guidance")

    sync_parser = subparsers.add_parser("sync", help="Sync conversations from a source")
    sync_parser.add_argument("source", choices=["codex", "claude-code"])
    sync_mode = sync_parser.add_mutually_exclusive_group()
    sync_mode.add_argument("--latest", type=int)
    sync_mode.add_argument("--all", action="store_true")

    hooks_parser = subparsers.add_parser("hooks", help="Manage Agent hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command", required=True)
    hooks_install = hooks_subparsers.add_parser("install", help="Install hooks")
    hooks_install.add_argument("source", choices=["codex", "claude-code"])
    hooks_install.add_argument("--project-root", default=".", help="Project root for Codex local hooks")
    hooks_install.add_argument("--claude-settings", help="Claude Code settings.json path")

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
            codex_changed = install_codex_hook(Path.cwd(), result.context_home)
            claude_changed = install_claude_code_hook(Path.home() / ".claude" / "settings.json", result.context_home)
            print(f"codex hook: {'updated' if codex_changed else 'unchanged'}")
            print(f"claude-code hook: {'updated' if claude_changed else 'unchanged'}")
        return 0

    if args.command == "sync":
        config = load_config(args.context_home)
        latest = args.latest
        if args.source == "codex":
            result = sync_codex(
                config.codex.sessions_dir,
                config.codex.output_dir,
                config.context_home / "state" / "codex-sync-state.json",
                latest=latest,
                all_sessions=args.all,
            )
            _print_result(result)
            return 0

        if args.source == "claude-code":
            result = sync_claude_code(
                config.claude_code.projects_dir,
                config.claude_code.output_dir,
                config.context_home / "state" / "claude-code-sync-state.json",
                latest=latest,
                all_sessions=args.all,
            )
            _print_result(result)
            return 0

    if args.command == "hooks" and args.hooks_command == "install":
        context_home = resolve_context_home(args.context_home)
        if args.source == "codex":
            project_root = Path(args.project_root).expanduser().resolve()
            changed = install_codex_hook(project_root, context_home)
            print(f"codex hook: {'updated' if changed else 'unchanged'}")
            return 0

        if args.source == "claude-code":
            settings_path = (
                Path(args.claude_settings).expanduser().resolve()
                if args.claude_settings
                else Path.home() / ".claude" / "settings.json"
            )
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
