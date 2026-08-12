# CLI reference

Power-user reference for **`astroai-lab`** (in-session workbench). Platform
session lifecycle uses the separate **`canfar`** CLI —
[opencadc.github.io/canfar](https://opencadc.github.io/canfar/).

`astroai-lab` is intentionally small: **environment save/resume** plus **AI
agent management**, with a few supporting commands (session status, notebook
kernel, shell env export).

Global flags (most commands accept these **before** the subcommand, e.g. `astroai-lab --json status`. Several commands also accept the same flags **after** the subcommand name — see examples below):

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable output |
| `--yes` / `-y` | Non-interactive; skip confirmations |
| `--dry-run` | Show actions without executing |
| `--quiet` / `-q` | Minimal output |
| `--version` / `-V` | Show version |

## Top-level commands

### `astroai-lab`

Brief status banner when invoked with no subcommand.

### `astroai-lab init NAME`

Create a pixi or uv project under the work directory.

```bash
astroai-lab init mylab
astroai-lab init mylab --uv --no-git
```

### `astroai-lab clone REPO`

Clone via `gh` and install dependencies.

```bash
astroai-lab clone owner/repo
astroai-lab clone --from-env ml-base owner/repo
```

### `astroai-lab save [NAME]`

Save lockfile manifest to `~/.astroai/lab/saves/`.

```bash
astroai-lab save
astroai-lab save mylab --full
```

### `astroai-lab resume NAME`

Restore a saved environment and run install.

```bash
astroai-lab resume mylab
astroai-lab resume mylab --from /arc/projects/team/env-saves/mylab
```

### `astroai-lab saves`

List saved environments.

```bash
astroai-lab saves
astroai-lab saves --json
```

### `astroai-lab status`

Quotas, home breakdown, team project membership, CANFAR auth/sessions, and top processes.

```bash
astroai-lab status
astroai-lab status --json
```

**`--json` keys:** `quotas`, `home`, `processes`, `canfar_auth`, `canfar_sessions`, `arc_project`, `arc_projects`, `gms_groups`, `vault`.

Each **`arc_projects[]`** entry includes `access` (`rw`/`ro`), `acl_groups` (from `getfacl`), `gms_member`, optional nested **`vault`** (VOSpace quota/groups), and `quota` (POSIX `df` on `/arc/projects/<name>`).

**`gms_groups`:** `{groups, source}` from `cadc-groups list` when cert/netrc is available, else `null`.

**`vault`:** `{service, source, auth, nodes[]}` from the vos API (`vault:/<name>`). Vault quotas may also appear in `quotas` as `"<name> (vault)"`.

Requires optional tools on PATH: `getfacl`, `cadc-groups` (CADC venv), `vos` — all ship in AstroAI session images.

### `astroai-lab help`

Print `--help` for the app and every subcommand — the aggregate of all help
output in registration order.

```bash
astroai-lab help                     # full dump (pages via less on a terminal)
astroai-lab help -c agent            # one command only
astroai-lab help --command "agent list"
astroai-lab help --json              # command inventory (machine-readable)
astroai-lab help -c status --json    # structured help for one command
```

Shell completion offers registered command paths for `-c` (bash/zsh/fish via
`astroai-lab --install-completion <shell>`). With `--json`, `help` prints a
command inventory (path, help, options, subcommands) or structured help for a
single `-c` path.

## Nested commands

### `astroai-lab env export`

Session shell infrastructure (applied automatically by `profile.sh` at login).

```bash
eval "$(astroai-lab env export)"
astroai-lab env export --json        # resolved env as a JSON object
astroai-lab --json env export        # same, via the global flag
```

With `--json`, prints the resolved session environment as a JSON object — the
same keys and values as the shell export, without `export KEY=...` syntax (useful
for `jq`, scripts, and tooling). `--no-ensure` skips creating cache/runtime
directories.

Image builds copy the packaged `profile.sh` / `hooks.sh` at build time —
`astroai-lab` itself stays an in-session tool.

### `astroai-lab config show|path`

Optional preferences file.

```bash
astroai-lab config show
astroai-lab config path
```

### `astroai-lab kernel ensure|register|list|unregister`

Jupyter kernels for notebook sessions.

```bash
astroai-lab kernel ensure              # scratch-safe default (no pixi project)
astroai-lab kernel register [PATH]     # project .pixi/.venv as kernel
astroai-lab kernel list
astroai-lab kernel unregister NAME
```

### `astroai-lab agent list|install|remove|wipe|setup|config|update|status|verify|plugins`

AI agent MCP, rules, skills, CLI installation, and plugins.

**`agent list` is the single installable set.** Every agent is one YAML file
under `data/agent/agents/<id>.yaml` (`id`, `name`, `homepage`, `binary`,
`install`, optional `config`, `verify`). `list` / `install` / `remove` /
`verify` all read that set. CLIs land on `$SCRATCH` (`$ASTROAI_LAB_BIN_DIR`);
configs stay on `$HOME` (/arc/home). Some ids still install via battle-tested
`install.TOOLS` branches (same id appears in the list). CLI utilities such as
`ast-grep` are installed via plugins (`ast-grep-cli`), not listed as agents.
`hyperfine` is image-baked and is not reinstalled.

Mental model (lean surface — list/install/remove/config + plugins):

| Command | What it does |
|---------|----------------|
| `agent list` | Installable agents: binary / config / source / version + one-line summary |
| `agent list config` | Skills/MCP/addons from the plugin registry (`--kind` filters) |
| `agent install [NAME]` | Download a CLI binary via the registry (omit NAME to list agents) |
| `agent remove NAME` | Uninstall managed CLI on scratch (`--clean-home` for `$HOME` CLIs; `--purge` for config dirs) |
| `agent wipe` | **Factory reset** — remove EVERY agent config + binary + state; confirmation or `--yes` |
| `agent setup [BUNDLE…]` | Write MCP/rules/skills configs (`--list` for bundles); registry agent id / `--all` / `--project` |
| `agent config ID` | Show/edit an agent's `$HOME` config (`--key`, `key=value`, `--unset`) |
| `agent update [ID]` | Refresh configs + upstream skills; with ID refreshes one agent |
| `agent status` | Same table as `list` (versions probed); `--ui` for container endpoints |
| `agent verify` | Health check; `--fix` auto-repairs shared setup + installed agents; `--fix ID` for one agent; `--fix --all` same as bare `--fix`; `--clean` stale state |
| `agent plugins …` | list / install / update / remove / configure plugins across agents |

```bash
astroai-lab agent list                 # registered agents
astroai-lab agent list config          # skills/MCP/addons
astroai-lab --json agent list          # --json is a global flag: BEFORE the subcommand
astroai-lab agent setup
astroai-lab agent setup --list
astroai-lab agent setup hermes         # per-agent registry setup
astroai-lab agent setup --all
astroai-lab agent setup --project ./repo   # per-repo AGENTS.md + .cursor
astroai-lab agent install              # list agents
astroai-lab agent install kilo
astroai-lab agent install zcode
astroai-lab agent install omp
astroai-lab agent remove kilo          # uninstall (--purge removes ~/.<agent> home dirs)
astroai-lab agent wipe --dry-run
astroai-lab agent wipe --yes
astroai-lab agent plugins list
astroai-lab agent plugins list --kind mcp
astroai-lab agent plugins install canfar-ray
astroai-lab agent plugins install canfar-ray --agent hermes
astroai-lab agent plugins remove canfar-ray
astroai-lab agent plugins configure ray-manager-mcp
astroai-lab agent verify
astroai-lab agent verify --fix         # auto-repair, then re-check
astroai-lab agent verify --fix hermes  # regenerate/sanitize ONE agent's config
astroai-lab agent verify --fix --all
astroai-lab agent verify --clean
astroai-lab agent config hermes
astroai-lab agent config hermes --key model
astroai-lab agent config hermes model=nousresearch/hermes-3-llama-3.1-405b
astroai-lab agent config openclaw --unset model
astroai-lab agent update               # full refresh after image upgrades
astroai-lab agent update hermes
astroai-lab agent update openclaw --reinstall
```

**Agent plugins** (`data/agent/plugins/*.yaml`) are the uniform surface for
skills / MCP servers / config snippets across *all* installed agents.
Each plugin declares a support matrix (`agents:`), a `kind`, and how it is
applied. `plugins install <id>` applies to every installed agent in the matrix
by default; `--agent` scopes it. `plugins configure <id>` for `kind: mcp`
merges an `mcpServers` entry — **dynamic URLs only** (e.g.
`$ASTROAI_RAY_JOBS_ADDRESS`).

**`ray-manager-mcp`** (the shipped `kind: mcp` example) configures
`astroai-workload mcp serve` with a runtime-resolved
`$ASTROAI_RAY_JOBS_ADDRESS`.

## Removed in 0.3 / agent lean cut

For a deeper rethink, `astroai-lab` no longer ships the following commands.
Use the platform tools instead:

| Removed | Replacement |
|---------|-------------|
| `data stage/sync` | `canfar data` (platform archive I/O) |
| `project init` | Project provisioning is done by operators; users read `/arc/projects` via `status` |
| `backup` | `git` + `astroai-lab save` (env snapshots) |
| `workspace` | `git` + `astroai-lab save` |
| `push` | `git push` + `astroai-lab save` |
| `clean` | Manual cache pruning; monitor with `status` |
| `doctor` | `status` / `env export` |
| `paths`/`tools`/`check` | `status` / `env export` |
| `notebook` | Starters ship at `/opt/astroai/notebooks/` in images |
| `ray` | AstroAI hub / OpenResearch batch compute |
| `env save/resume/list` | Flat `save`/`resume`/`saves` |
| `env install-shell` | Image builds copy packaged `profile.sh`/`hooks.sh` at build time |
| `guide` | Renamed to `help` (aggregate of all `--help`) |
| `agent sync` / `agent sources` / `agent skills` | `agent update` |
| `agent catalog` / `agent awesome` / `agent directory` / `agent list --all` | `agent list` / `agent list config` |
| `agent addons` / `agent add` | `agent plugins list` / `agent plugins install` |
| `agent project` | `agent setup --project` |
| `agent fix-config` / `agent fix` / `agent clean` / `agent repair` | `agent verify --fix` / `agent verify --clean` |
| `agent report` | `agent status --json` |
| `agent interact` / `agent access` | `agent status --ui` |

## Environment variables

`astroai-lab` speaks the same storage vocabulary as typical HPC/Slurm clusters:
`WORK`, `SCRATCH`, `PROJECT` are the canonical names. Session paths are applied
in login shells via `astroai-lab env export` (bundled in
`/etc/astroai-lab/profile.sh` on CANFAR images). Skaha sessions provide
`WORK`/`SCRATCH`; `PROJECT` is detected from the current dir under `/arc/projects`
or set explicitly.

### Session paths (Slurm-style)

| Variable | Purpose |
|----------|---------|
| `WORK` | Session work dir; code and project envs live here (Skaha: `/srcdir`) |
| `SCRATCH` | Session scratch; data, caches, runtime installs (Skaha: `/scratch`) |
| `PROJECT` | Team project dir (e.g. `/arc/projects/<group>`); used for team tools and env saves |

### Path overrides

| Variable | Purpose |
|----------|---------|
| `WORK` / `SCRATCH` / `PROJECT` | Set explicitly to override detected session paths |
| `ASTROAI_LAB_SAVE_DIR` | Env saves dir (default: `~/.astroai/lab/saves`) |
| `ASTROAI_LAB_BIN_DIR` | User CLI install dir (default: scratch `.local/bin`; last resort: work `.runtime-$USER/bin` — never `~/.local`) |
| `ASTROAI_LAB_RUNTIME_ROOT` | Runtime uv/pixi/mamba roots (default: scratch `.runtime-$USER`) |
| `ASTROAI_LAB_NPM_PREFIX` | npm global prefix (default: `.local` under scratch) |
| `NPM_CONFIG_PREFIX` | Fallback npm prefix when `ASTROAI_LAB_NPM_PREFIX` is unset |
| `ASTROAI_LAB_CONFIG_DIR` | Workbench config dir (default: `~/.astroai/lab`) |
| `ASTROAI_LAB_PYTHONPATH` | Extra `PYTHONPATH` entries (colon-separated) |
| `PYTHONPATH` | Existing entries are preserved and merged into the export |

### XDG, cache, and runtime dirs

Defaults below apply when scratch is mounted (the CANFAR session case); without
scratch, caches fall back to `$HOME`-side paths (e.g. `XDG_CACHE_HOME` → `~/.cache`).

| Variable | Purpose |
|----------|---------|
| `XDG_CONFIG_HOME` | XDG config base (default: `~/.config`) |
| `XDG_DATA_HOME` | XDG data base (default: `~/.local/share`) |
| `XDG_CACHE_HOME` | XDG cache base (default: scratch cache root) |
| `UV_CACHE_DIR` | `uv` cache (default: scratch `uv/`) |
| `PIP_CACHE_DIR` | `pip` cache (default: scratch `pip/`) |
| `PIXI_CACHE_DIR` | `pixi` cache (default: scratch `pixi/`) |
| `NPM_CONFIG_CACHE` | npm cache (default: scratch `npm/`) |
| `HF_HOME` | Hugging Face cache (default: scratch `huggingface/`) |
| `TORCH_HOME` | PyTorch cache (default: scratch `torch/`) |
| `TMPDIR` | Temp dir (default: scratch `.tmp-$USER`) |
| `UV_LINK_MODE` | `uv` link mode (default: `copy`) |

### Runtime roots and conda cache (uv/pixi/mamba)

These are redirected to `ASTROAI_LAB_RUNTIME_ROOT` (default: scratch
`.runtime-$USER`) at session time, even though the image sets system-prefix
build-time defaults.

| Variable | Purpose |
|----------|---------|
| `PIXI_HOME` | pixi home (default: runtime `pixi/`) |
| `MAMBA_ROOT_PREFIX` | micromamba root (default: runtime `micromamba/`) |
| `UV_PYTHON_INSTALL_DIR` | uv-managed Pythons (default: runtime `uv/python/`) |
| `UV_TOOL_DIR` | uv tool installs (default: runtime `uv/tools/`) |
| `MAMBA_PKGS_DIRS` / `CONDA_PKGS_DIRS` | conda package cache (default: scratch `conda/pkgs/`) |

### Preferences (also settable in `config.yaml`)

| Variable | Purpose |
|----------|---------|
| `ASTROAI_LAB_DEFAULT_PM` | Default package manager: `pixi` or `uv` (default: `pixi`) |
| `ASTROAI_LAB_CLONE_FROM_ENV` | Default env preset for `astroai-lab clone` |

### AI agent management

| Variable | Purpose |
|----------|---------|
| `ASTROAI_LAB_AGENT_BUNDLE` | Override the agent bundle root |
| `ASTROAI_LAB_AGENT_GIT_TIMEOUT` | Git-op timeout, seconds (default: `120`) |
| `ASTROAI_LAB_AGENT_INSTALL_TIMEOUT` | CLI-install timeout, seconds (default: `1500`; self-bootstrapping installers like hermes need more than 300) |
| `ASTROAI_LAB_AGENT_LOCK_TIMEOUT` | Setup-lock timeout, seconds (default: `30`) |
| `ASTROAI_SESSION_KIND` | Session kind label for `agent status --ui` (default: `unknown`) |
| `ASTROAI_AGENT_WIZARD_PORT` | Agent wizard port (default: `4792`) |
| `ASTROAI_OPENWORKER_PORT` | OpenWorker port (default: `5000`) |

### Shell integration

| Variable | Purpose |
|----------|---------|
| `ASTROAI_LAB_SHELL_DIR` | Dir holding `profile.sh`/`hooks.sh` (default: `/etc/astroai-lab`) |
| `ASTROAI_LAB_PROFILE_LOADED` | Set by `profile.sh` to avoid double-sourcing |
| `JUPYTER_CONFIG_DIR` | Jupyter config dir (default: `~/.jupyter`) |
| `USER` / `HOSTNAME` | Identity labels used by `status` and `agent status --ui` |

`astroai-lab env export` also **emits** derived values for downstream tools,
including `ASTROAI_LAB_TEAM_BIN` (when a team project is present),
`ASTROAI_LAB_PATH_PREFIX` (consumed by the image's `/etc/profile.d/astroai.sh`),
`UV_PYTHON_BIN_DIR`, `UV_TOOL_BIN_DIR` (both pointing at `ASTROAI_LAB_BIN_DIR`),
`PYTHONUSERBASE`, `TRANSFORMERS_CACHE`, `HF_DATASETS_CACHE`, and
`MPLCONFIGDIR`.

See [config.md](config.md) for optional YAML preferences.
