# context-harness

[中文文档](README.zh-CN.md)

`context-harness` is a local-first personal AI context tool. It archives conversations from your local AI coding assistants so they can be synced, searched, and turned into useful memory later.

V1 currently supports two common local AI coding assistants:

- Codex
- Claude Code

The project keeps the tool itself separate from your personal data. This repository contains the program; your conversations, memory, logs, and sync state live in a configurable data directory such as `~/.context-harness`.

## Simple Install

If you just want to get it working, you do not need to understand plugins, skills, or command-line internals first. Start with one of these two paths. After installation, you will have:

- Personal data folder: `~/.context-harness`
- Program runtime folder: `~/.local/share/context-harness`
- Automatic sync settings for Codex / Claude Code when the installer detects them, or when you explicitly request them

### Option A: Copy One Command

On macOS / Linux, paste this into Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | bash
```

If you only want to turn on automatic sync for one AI coding assistant, use:

```bash
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | env CONTEXT_HARNESS_AGENTS=codex bash
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | env CONTEXT_HARNESS_AGENTS=claude-code bash
```

The installer prepares `uv`, downloads or updates `context-harness`, initializes the data folder, and turns on the selected sync settings. If Codex asks you to approve the sync hook after installation, run `/hooks` in Codex and approve `context-harness`.

### Option B: Ask Your Local AI Coding Assistant

If you do not want to manage the terminal steps yourself, copy this prompt into your local Codex, Claude Code, or another AI coding assistant:

```text
Please install context-harness on this machine so it can sync and archive my local AI coding assistant conversations.

Please run this one-line installer first:
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | bash

After installation, tell me:
1. Whether the personal data folder was created at ~/.context-harness
2. Whether the program runtime folder is ready at ~/.local/share/context-harness
3. Which automatic sync settings were turned on for Codex / Claude Code
4. If Codex needs hook trust approval, remind me to run /hooks and approve context-harness

Do not store my conversations, memory, or sync state inside the context-harness source repository.
```

If you already know that you only use Codex or only use Claude Code, change the installer command to:

```bash
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | env CONTEXT_HARNESS_AGENTS=codex bash
curl -fsSL https://raw.githubusercontent.com/yinjialu/context-harness/main/scripts/install.sh | env CONTEXT_HARNESS_AGENTS=claude-code bash
```

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
uv run context-harness --context-home ~/.context-harness hooks install codex
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

## Codex Plugin

This repository is also a Codex plugin. Its plugin manifest lives at `.codex-plugin/plugin.json` and exposes the repository's `skills/` directory.

### Public community install

Codex does not currently support self-serve publishing into the official public Plugin Directory. For community distribution, publish the Git marketplace and ask users to add it once:

```bash
codex plugin marketplace add yinjialu/context-harness --ref codex-plugin
```

After adding the marketplace, users can open the Codex Plugins page, switch to the `Context Harness` marketplace source, search for `context-harness`, and install it there. They can also install it from the CLI:

```bash
codex plugin add context-harness@context-harness
```

Update an existing installation:

```bash
codex plugin marketplace upgrade context-harness
codex plugin add context-harness@context-harness
```

### Workspace sharing

To make the plugin installable directly from the Codex app for teammates in the same ChatGPT workspace:

1. Install the plugin locally.
2. Open the Codex Plugins page.
3. Go to `Created by you` and open `Context Harness`.
4. Select `Share`.
5. Add workspace members or groups, or copy a share link.

People you share with can find the plugin under `Shared with you` in the Codex plugin directory. Workspace sharing does not publish the plugin to the public Plugin Directory.

### Publishing the marketplace branch

The `codex-plugin` branch is generated from this repository by `scripts/build_codex_plugin_marketplace.py`. Maintainers can publish it manually:

```bash
python3 scripts/build_codex_plugin_marketplace.py
cd dist/codex-plugin-marketplace
git init
git add .
git commit -m "Publish Codex plugin marketplace"
git branch -M codex-plugin
git remote add origin git@github.com:yinjialu/context-harness.git
git push --force origin codex-plugin
```

The GitHub Actions workflow also publishes that branch when a `v*` tag is pushed, or when the workflow is run manually.

For local development, register the current checkout through the personal Codex marketplace:

```bash
mkdir -p ~/plugins
ln -sfn /path/to/context-harness ~/plugins/context-harness
codex plugin add context-harness@personal
```

The symlink keeps the current repository as the single source of truth while matching Codex's standard personal marketplace path layout.

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

## Claude Code Plugin

This repository is also a Claude Code plugin. Its plugin manifest lives at `.claude-plugin/plugin.json`, and Claude Code auto-discovers the repository's `skills/` directory.

### Community install

Publish the Git marketplace and ask users to add it once:

```bash
/plugin marketplace add yinjialu/context-harness#claude-plugin
```

Then install the plugin from the marketplace:

```bash
/plugin install context-harness@context-harness
```

You can also drive the same flow from the CLI:

```bash
claude plugin marketplace add yinjialu/context-harness#claude-plugin
claude plugin install context-harness@context-harness
```

Update an existing installation:

```bash
claude plugin marketplace update context-harness
claude plugin update context-harness@context-harness
```

### Publishing the marketplace branch

The `claude-plugin` branch is generated from this repository by `scripts/build_claude_plugin_marketplace.py`. Maintainers can publish it manually:

```bash
python3 scripts/build_claude_plugin_marketplace.py
cd dist/claude-plugin-marketplace
git init
git add .
git commit -m "Publish Claude Code plugin marketplace"
git branch -M claude-plugin
git remote add origin git@github.com:yinjialu/context-harness.git
git push --force origin claude-plugin
```

The `Publish Claude Code Plugin Marketplace` GitHub Actions workflow also publishes that branch when a `v*` tag is pushed, or when the workflow is run manually.

For local development, add the current checkout as a local marketplace:

```bash
/plugin marketplace add /path/to/context-harness
/plugin install context-harness@context-harness
```

Claude Code reads `.claude-plugin/plugin.json` directly from the checkout, so the repository stays the single source of truth.

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
gh skill publish skills --tag v0.1.8
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
- checks out `v0.1.8` by default
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

## Audit Local Version

Use these read-only checks before and after upgrading a machine:

```bash
context-harness --version
readlink ~/.context-harness
git -C ~/.local/share/context-harness describe --tags --always --dirty
git -C ~/.local/share/context-harness status --short
rg "context-harness" ~/.codex/hooks.json ~/.claude/settings.json
```

For a smooth upgrade, publish a tagged release first, then rerun the skill bootstrap once. The bootstrap updates `~/.local/share/context-harness` to the default tag baked into the installed skill unless `CONTEXT_HARNESS_REF` overrides it:

```bash
bash ~/.agents/skills/sync-conversations/scripts/bootstrap.sh
context-harness --version
```

## Hooks

V1 hooks automatically call the sync command at the right point in Codex and Claude Code lifecycle, then archive the new conversation into `context_home`.

Hook installers use the same scope model for supported Code Agents: user-level by default, project-local when `--scope project` is passed. `--project-root` targets a different project; otherwise project-local install uses the current directory.

Codex hooks are written to `~/.codex/config.toml` and `~/.codex/hooks.json` by default:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex
```

To install a project-local Codex hook instead, pass `--scope project`. From the target project root:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --scope project
```

If you run the command from the `context-harness` repository root for another project, pass the target project explicitly:

```bash
uv run context-harness --context-home ~/.context-harness hooks install codex --scope project --project-root /path/to/your-codex-project
```

Claude Code hooks are written to `~/.claude/settings.json` by default:

```bash
uv run context-harness --context-home ~/.context-harness hooks install claude-code
```

To install a project-local Claude Code hook:

```bash
uv run context-harness --context-home ~/.context-harness hooks install claude-code --scope project
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
uv run context-harness --context-home ~/.context-harness hooks install codex
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
