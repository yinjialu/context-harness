# context-harness

[中文文档](README.zh-CN.md)

`context-harness` is a local-first personal AI context loop for Code Agent conversations.

V1 focuses on two local Code Agent sources:

- Codex
- Claude Code

The project separates the mechanism layer from the user data layer. This repository contains only the CLI, skills, hook installers, templates, docs, and tests. Conversations, memory, logs, and sync state live in a configurable data directory such as `~/.context-harness`.

## Quick Start

Run the following commands from the `context-harness` repository root.

Clone the repository:

```bash
git clone https://github.com/yinjialu/context-harness.git
cd context-harness
```

Install dependencies:

```bash
uv sync
```

Initialize the data home:

```bash
uv run context-harness --context-home ~/.context-harness init
```

Sync the latest Codex conversation:

```bash
uv run context-harness --context-home ~/.context-harness sync codex --latest 1
```

Sync the latest Claude Code conversation:

```bash
uv run context-harness --context-home ~/.context-harness sync claude-code --latest 1
```

Install automatic sync hooks:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

## Custom Data Home

`context-harness` supports two ways to set the data home:

```bash
CONTEXT_HARNESS_HOME=~/Documents/my-context uv run context-harness init
uv run context-harness --context-home ~/Documents/my-context init
```

`--context-home` takes precedence over `CONTEXT_HARNESS_HOME`. After initialization, edit `config.toml` in the data home to customize Codex / Claude Code source paths and archive output paths.

Example:

```toml
[sources.codex]
enabled = true
sessions_dir = "~/Library/Application Support/Codex/sessions"
output_dir = "conversations/codex"

[sources.claude-code]
enabled = true
projects_dir = "~/Documents/claude-code-projects"
output_dir = "conversations/claude-code"

[memory]
profile_file = "memory/user_profile.md"
global_context_file = "global-claude.md"
```

Relative paths are resolved against `context_home`. Absolute paths and `~` keep their normal meaning.

## Data Directory Layout

After initialization, the data home looks roughly like this:

```text
~/.context-harness/
  config.toml
  global-claude.md
  conversations/
    codex/
    claude-code/
  memory/
    MEMORY.md
    user_profile.md
  state/
    codex-sync-state.json
    claude-code-sync-state.json
```

- `conversations/` stores Markdown archives rendered from Code Agent transcripts.
- `memory/` stores files maintained by workflows such as `profile-dreamer`.
- `state/` stores incremental sync state to avoid reprocessing unchanged sessions.
- `config.toml` describes local machine paths and switches. It should not be committed to this mechanism repository.

## Skills

This repository includes three Agent-facing skills:

- `skills/init-context`: initialize the data home and optionally install Codex / Claude Code hooks.
- `skills/sync-conversations`: manually run full or incremental conversation sync.
- `skills/profile-dreamer`: extract profile and memory update proposals from archived conversations.

The skills describe Agent workflows. The CLI owns the actual behavior, so business logic stays in one place.

For repo-local discovery, the repository also provides relative symlinks:

```text
.agents/skills/      # Codex repo-local skills
.claude/skills/      # Claude Code repo-local skills
```

To install the skills globally, run:

```bash
mkdir -p ~/.agents/skills ~/.claude/skills
ln -sfn /path/to/context-harness/skills/init-context ~/.agents/skills/init-context
ln -sfn /path/to/context-harness/skills/sync-conversations ~/.agents/skills/sync-conversations
ln -sfn /path/to/context-harness/skills/profile-dreamer ~/.agents/skills/profile-dreamer
ln -sfn /path/to/context-harness/skills/init-context ~/.claude/skills/init-context
ln -sfn /path/to/context-harness/skills/sync-conversations ~/.claude/skills/sync-conversations
ln -sfn /path/to/context-harness/skills/profile-dreamer ~/.claude/skills/profile-dreamer
```

## Install With skills.sh / gh skill

The repository follows the standard `skills/*/SKILL.md` layout, so skill tooling can install it directly from GitHub.

Install all skills for Codex and Claude Code with `npx skills`:

```bash
npx skills add yinjialu/context-harness --skill '*' -a codex -a claude-code -g -y
```

Install with GitHub CLI `gh skill`:

```bash
for skill in init-context sync-conversations profile-dreamer; do
  gh skill install yinjialu/context-harness "$skill" --agent codex --scope user
  gh skill install yinjialu/context-harness "$skill" --agent claude-code --scope user
done
```

Validate the publishable skill package:

```bash
gh skill publish skills --dry-run
```

Publish a tagged release:

```bash
gh skill publish skills --tag v0.1.4
```

`skills/` is the canonical publish target. Running `gh skill publish` from the repository root may warn about `.agents/skills` and `.claude/skills`; those directories are intentionally kept as repo-local discovery symlinks for Codex and Claude Code.

## Skill-Only Bootstrap

Installing the skills does not copy the whole CLI repository into the agent's skill directory. To close that gap, each skill includes `scripts/bootstrap.sh`.

When an Agent runs a context-harness skill, it should first run:

```bash
runtime_dir="$(bash scripts/bootstrap.sh)"
cd "$runtime_dir"
```

The bootstrap script:

- clones or updates the runtime repository at `~/.local/share/context-harness`
- checks out `v0.1.4` by default
- runs `uv sync`
- prints the runtime repository path on stdout

After that, the Agent can run normal CLI commands:

```bash
uv run context-harness --context-home ~/.context-harness init
uv run context-harness --context-home ~/.context-harness sync codex --latest 1
```

Forks can override the runtime source:

```bash
CONTEXT_HARNESS_REPO_URL=https://github.com/<owner>/<repo>.git \
CONTEXT_HARNESS_REF=main \
bash scripts/bootstrap.sh
```

You can also set `CONTEXT_HARNESS_RUNTIME_DIR` to choose a custom runtime checkout path.

## Hooks

V1 hooks automatically call the sync command at the right point in Codex and Claude Code lifecycle, then archive the new conversation into `context_home`.

Codex hooks are project-local. They write `.codex/config.toml` and `.codex/hooks.json` in the target project. If you run the command from the target project root, `--project-root` can be omitted:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex
```

If you run the command from the `context-harness` repository root for another project, pass the target project explicitly:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
```

Claude Code hooks are written to `~/.claude/settings.json` by default:

```bash
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

Hook installers are idempotent. Re-running them updates the existing context-harness sync hook without deleting unrelated hook configuration.

The generated hook command reads `transcript_path` from hook stdin and syncs the transcript that just ended, instead of guessing the latest conversation by global mtime. The command stores the absolute path to this `context-harness` checkout; reinstall hooks after moving or deleting the repository.

Codex command hooks may require an additional trust review. If Codex reports that the hook is untrusted, run `/hooks` in Codex and approve the `context-harness` hook.

## Using With Codex

Codex discovers skills from repo-local `.agents/skills/` and user-level `$HOME/.agents/skills`. When you open the `context-harness` repository, the built-in skills are exposed through `.agents/skills`. To use them from any project, install them globally into `~/.agents/skills`.

Typical invocations:

```text
$init-context initialize context-harness and optionally install hooks
$sync-conversations sync Codex / Claude Code conversation records
$profile-dreamer propose memory / profile updates from archived conversations
```

Natural language works too:

```text
Use sync-conversations to sync recent Codex and Claude Code conversations
Use profile-dreamer to extract changes in my personal profile from recent archives
```

Recommended setup:

```bash
uv run context-harness --context-home ~/.context-harness init
uv run context-harness --context-home ~/.context-harness hooks install codex --project-root /path/to/your-codex-project
```

Then run `/hooks` in Codex and trust the `context-harness` command hook. After that, the Codex Stop hook passes `transcript_path` to `context-harness`, and the current transcript is archived first.

## Using With Claude Code

Claude Code discovers project skills from `.claude/skills/` and user skills from `~/.claude/skills`. When you open the `context-harness` repository, the built-in skills are exposed through `.claude/skills`. To use them from any project, install them globally into `~/.claude/skills`.

Typical invocations:

```text
/init-context
/sync-conversations
/profile-dreamer
```

Recommended setup:

```bash
uv run context-harness --context-home ~/.context-harness init
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

The Claude Code hook is written to `~/.claude/settings.json` by default. The Stop hook reads transcript information from hook stdin and archives the current session into `~/.context-harness/conversations/claude-code/`.

## Design Docs

- [docs/superpowers/specs/2026-06-16-context-harness-design.md](docs/superpowers/specs/2026-06-16-context-harness-design.md)
- [docs/superpowers/plans/2026-06-16-context-harness-v1-core.md](docs/superpowers/plans/2026-06-16-context-harness-v1-core.md)

## License

MIT
