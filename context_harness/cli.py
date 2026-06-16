from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-harness",
        description="Local-first personal AI context loop for Code Agent conversations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize context-harness data home")

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
        parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
