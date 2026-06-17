#!/usr/bin/env bash
set -euo pipefail

repo_url="${CONTEXT_HARNESS_REPO_URL:-https://github.com/yinjialu/context-harness.git}"
runtime_dir="${CONTEXT_HARNESS_RUNTIME_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/context-harness}"
runtime_ref="${CONTEXT_HARNESS_REF:-v0.1.2}"
skip_update="${CONTEXT_HARNESS_BOOTSTRAP_SKIP_UPDATE:-0}"

log() {
  printf '%s\n' "$*" >&2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

require_command git
require_command uv

runtime_parent="$(dirname "$runtime_dir")"
mkdir -p "$runtime_parent"

if [ -e "$runtime_dir" ] && [ ! -d "$runtime_dir/.git" ]; then
  log "Runtime path exists but is not a git checkout: $runtime_dir"
  log "Set CONTEXT_HARNESS_RUNTIME_DIR to another path or move the existing directory."
  exit 1
fi

if [ ! -d "$runtime_dir/.git" ]; then
  log "Cloning context-harness runtime into $runtime_dir"
  git clone "$repo_url" "$runtime_dir" >&2
fi

cd "$runtime_dir"

if [ "$skip_update" != "1" ]; then
  log "Updating context-harness runtime"
  git fetch --tags --prune origin >&2
fi

if [ -n "$runtime_ref" ]; then
  log "Checking out $runtime_ref"
  git checkout --quiet "$runtime_ref"
elif [ "$skip_update" != "1" ]; then
  log "Fast-forwarding current branch"
  git pull --ff-only >&2
fi

log "Preparing Python environment with uv"
uv sync >&2

printf '%s\n' "$runtime_dir"
