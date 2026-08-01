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

### `astroai-lab agent setup|update|addons|add|skills|project|verify|fix|clean|interact|list|install|models|status`

AI agent MCP, rules, skills, CLI installation, curated catalog, auto-fix, state clean, and free model presets.

Mental model:

| Command | What it does |
|---------|----------------|
| `agent catalog` | Curated Catalog & Directory of agents, skills, rules, MCP servers, container UIs |
| `agent list` | Overview: installable CLIs, config bundles, Cursor skills |
| `agent install [TOOL]` | Download a CLI binary (omit TOOL to list) |
| `agent setup [BUNDLE…]` | Write MCP/rules/skills configs (`--list` for bundles) |
| `agent addons` | Curated lean + science addons (skills/rules/MCP) |
| `agent add NAME…` | Install curated addon(s); `--tag lean` / `--tag science` |
| `agent skills list` | Cursor skill inventory (bundled / GitHub / pixi / extras) |
| `agent skills update` | Refresh GitHub upstream skills only |
| `agent status` | Binaries + configs at a glance |
| `agent verify` | Presence checks **and** JSON/TOML/YAML syntax of configs (use `--fix` to auto-repair) |
| `agent fix` | Auto-repair syntax errors, missing directories, and stale locks |
| `agent clean` | Clean stale locks, failed markers, empty configs, and setup logs |
| `agent interact` | Inspect active container UI endpoints, open ports, and active agent CLIs |
| `agent models free` | OpenRouter / Kilo free-tier presets |

```bash
astroai-lab agent list
astroai-lab agent setup
astroai-lab agent setup --list
astroai-lab agent install              # list CLIs
astroai-lab agent install kilo
astroai-lab agent install qoder
astroai-lab agent addons               # curated recommendations
astroai-lab agent addons --tag lean
astroai-lab agent add ponytail
astroai-lab agent add polars modern-python
astroai-lab agent add --tag lean
astroai-lab agent skills list
astroai-lab agent skills update
astroai-lab agent verify
astroai-lab agent update               # full refresh after image upgrades
astroai-lab agent models free
astroai-lab agent models free --preset long
```

## Removed in 0.3

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
| `agent sync` | `agent update` |
| `agent sources` | `agent skills` |
| `agent awesome` / `agent directory` | `agent catalog` |
| `agent access` | `agent interact` |

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
| `ASTROAI_LAB_BIN_DIR` | User CLI install dir (default: scratch `.local/bin`) |
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
| `ASTROAI_LAB_AGENT_INSTALL_TIMEOUT` | CLI-install timeout, seconds (default: `300`) |
| `ASTROAI_LAB_AGENT_LOCK_TIMEOUT` | Setup-lock timeout, seconds (default: `30`) |
| `ASTROAI_SESSION_KIND` | Session kind label for `agent interact` (default: `unknown`) |
| `ASTROAI_AGENT_WIZARD_PORT` | Agent wizard port (default: `4792`) |
| `ASTROAI_OPENWORKER_PORT` | OpenWorker port (default: `5000`) |
| `OPENROUTER_API_KEY` (or `OPENROUTER_KEY`) | OpenRouter key for `agent models free` presets |

### Shell integration

| Variable | Purpose |
|----------|---------|
| `ASTROAI_LAB_SHELL_DIR` | Dir holding `profile.sh`/`hooks.sh` (default: `/etc/astroai-lab`) |
| `ASTROAI_LAB_PROFILE_LOADED` | Set by `profile.sh` to avoid double-sourcing |
| `JUPYTER_CONFIG_DIR` | Jupyter config dir (default: `~/.jupyter`) |
| `USER` / `HOSTNAME` | Identity labels used by `status` and `agent interact` |

`astroai-lab env export` also **emits** derived values for downstream tools,
including `ASTROAI_LAB_TEAM_BIN` (when a team project is present),
`ASTROAI_LAB_PATH_PREFIX` (consumed by the image's `/etc/profile.d/astroai.sh`),
`UV_PYTHON_BIN_DIR`, `UV_TOOL_BIN_DIR` (both pointing at `ASTROAI_LAB_BIN_DIR`),
`PYTHONUSERBASE`, `TRANSFORMERS_CACHE`, `HF_DATASETS_CACHE`, and
`MPLCONFIGDIR`.

See [config.md](config.md) for optional YAML preferences.
