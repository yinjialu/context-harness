#!/usr/bin/env bash
set -euo pipefail

repo_url="${CONTEXT_HARNESS_REPO_URL:-https://github.com/yinjialu/context-harness.git}"
runtime_dir="${CONTEXT_HARNESS_RUNTIME_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/context-harness}"
runtime_ref="${CONTEXT_HARNESS_REF:-}"
context_home="${CONTEXT_HARNESS_HOME:-$HOME/.context-harness}"
agents="${CONTEXT_HARNESS_AGENTS:-auto}"

log() {
  printf '%s\n' "$*" >&2
}

download() {
  url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$url"
  else
    log "Missing curl or wget. Please install one of them, then rerun this command."
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  log "uv was not found; installing uv with the official Astral installer."
  download "https://astral.sh/uv/install.sh" | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

  if ! command -v uv >/dev/null 2>&1; then
    log "uv was installed, but it is not available on PATH yet."
    log "Open a new terminal and rerun this installer, or add ~/.local/bin to PATH."
    exit 1
  fi
}

normalize_agents() {
  printf '%s' "$agents" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]'
}

agent_requested() {
  agent="$1"
  normalized_agents="$(normalize_agents)"

  case "$normalized_agents" in
    ""|"auto")
      if [ "$agent" = "codex" ]; then
        command -v codex >/dev/null 2>&1 || [ -d "$HOME/.codex" ]
      else
        command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]
      fi
      return
      ;;
    "all"|"both")
      return 0
      ;;
    "none"|"false"|"0")
      return 1
      ;;
  esac

  case ",$normalized_agents," in
    *",$agent,"*) return 0 ;;
    *",claude,"*) [ "$agent" = "claude-code" ] && return 0 ;;
  esac

  return 1
}

require_command git
ensure_uv

runtime_parent="$(dirname "$runtime_dir")"
mkdir -p "$runtime_parent"

if [ -e "$runtime_dir" ] && [ ! -d "$runtime_dir/.git" ]; then
  log "Runtime path exists but is not a git checkout: $runtime_dir"
  log "Set CONTEXT_HARNESS_RUNTIME_DIR to another path or move the existing directory."
  exit 1
fi

if [ ! -d "$runtime_dir/.git" ]; then
  log "Cloning context-harness into $runtime_dir"
  git clone "$repo_url" "$runtime_dir" >&2
fi

cd "$runtime_dir"

log "Updating context-harness"
git fetch --tags --prune origin >&2

if [ -z "$runtime_ref" ]; then
  runtime_ref="$(git tag -l 'v*' --sort=-v:refname | head -n1)"
fi

if [ -n "$runtime_ref" ]; then
  log "Checking out $runtime_ref"
  git checkout --quiet "$runtime_ref"
else
  log "No release tags found; fast-forwarding current branch"
  git pull --ff-only >&2
fi

log "Preparing Python environment"
uv sync >&2

log "Initializing context home at $context_home"
uv run context-harness --context-home "$context_home" init

codex_hook="skipped"
claude_hook="skipped"

if agent_requested "codex"; then
  log "Installing Codex hook"
  uv run context-harness --context-home "$context_home" hooks install codex
  codex_hook="installed"
fi

if agent_requested "claude-code"; then
  log "Installing Claude Code hook"
  uv run context-harness --context-home "$context_home" hooks install claude-code
  claude_hook="installed"
fi

cat <<EOF

context-harness is ready.
Runtime repo: $runtime_dir
Data home:    $context_home
Codex hook:   $codex_hook
Claude hook:  $claude_hook

If Codex asks you to trust the hook, run /hooks in Codex and approve context-harness.
EOF
