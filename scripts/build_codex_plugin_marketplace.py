#!/usr/bin/env python3
"""Build a Codex plugin marketplace directory for distribution."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PLUGIN_NAME = "context-harness"
MARKETPLACE_NAME = "context-harness"
MARKETPLACE_DISPLAY_NAME = "Context Harness"
EXCLUDED_NAMES = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "context-home",
    "dist",
}
EXCLUDED_SUFFIXES = {
    ".egg-info",
    ".pyc",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a distributable Codex plugin marketplace tree."
    )
    parser.add_argument(
        "--output",
        default="dist/codex-plugin-marketplace",
        help="Output directory for the generated marketplace tree.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output).resolve()
    plugin_root = output_root / "plugins" / PLUGIN_NAME

    manifest_path = repo_root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME:
        raise SystemExit(
            f"Expected plugin name {PLUGIN_NAME!r}, got {manifest.get('name')!r}."
        )

    if output_root.exists():
        shutil.rmtree(output_root)
    plugin_root.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(
        repo_root,
        plugin_root,
        ignore=ignore_paths,
        dirs_exist_ok=True,
    )

    marketplace_dir = output_root / ".agents" / "plugins"
    marketplace_dir.mkdir(parents=True, exist_ok=True)
    marketplace = {
        "name": MARKETPLACE_NAME,
        "interface": {
            "displayName": MARKETPLACE_DISPLAY_NAME,
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{PLUGIN_NAME}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }
    (marketplace_dir / "marketplace.json").write_text(
        json.dumps(marketplace, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_root)


def ignore_paths(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in EXCLUDED_NAMES:
            ignored.add(name)
            continue
        if name.startswith(".context-harness"):
            ignored.add(name)
            continue
        if any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
            ignored.add(name)
    return ignored


if __name__ == "__main__":
    main()
