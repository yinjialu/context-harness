from __future__ import annotations

import argparse
from collections.abc import Sequence

from .init import initialize_context_home


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
        for name, status in result.statuses.items():
            print(f"{name}: {status}")
        if args.install_hooks:
            print("hook installation is not implemented yet")

    return 0


def entrypoint() -> None:
    raise SystemExit(main())
