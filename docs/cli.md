# CLI reference

Power-user reference for **`astroai-lab`** (in-session workbench). Platform
session lifecycle uses the separate **`canfar`** CLI —
[opencadc.github.io/canfar](https://opencadc.github.io/canfar/).

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

### `astroai-lab push`

End-of-session: git push (if repo) + env save + summary.

```bash
astroai-lab push
astroai-lab push --yes --name mylab
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

### `astroai-lab paths`

Resolved session paths (work, scratch, caches, saves, cwd).

```bash
astroai-lab paths
astroai-lab paths --json
```

### `astroai-lab tools`

Inventory of common session tools on PATH, with versions when available.

```bash
astroai-lab tools
astroai-lab tools --json
```

### `astroai-lab check`

Quick health check: writable work/scratch/save paths plus `git` and `astroai-lab`. Exit code `1` on failure. Use **`--strict`** to also require recommended tools (`pixi`, `uv`, `gh`, `rg`, `jq`, `canfar`).

```bash
astroai-lab check
astroai-lab check --json
astroai-lab check --strict
```

### `astroai-lab doctor`

Full paths and tools report.

```bash
astroai-lab doctor --json
```

### `astroai-lab guide`

Print session workflow cheat sheet.

## Nested commands

### `astroai-lab env save|resume|list`

Backward-compatible aliases for flat commands.

### `astroai-lab data stage|sync`

Stage data from `/arc` to scratch or sync back.

```bash
astroai-lab data stage /arc/home/user/data
astroai-lab data sync /scratch/out /arc/home/user/data
astroai-lab data stage /arc/path --dry-run
astroai-lab data sync /scratch/out /arc/path --yes
```

### `astroai-lab backup run|start|stop|status|restore`

Hourly (default) rsync of the ephemeral work directory (`TMP_SRC_DIR` / `/srcdir`)
to `~/.astroai/lab/backups/<skaha_sessionid>/` on `/arc/home`. Session startup
starts the daemon automatically (`astroai-lab backup start`).

```bash
astroai-lab backup status
astroai-lab backup run
astroai-lab backup start --interval 21600   # every 6 hours
astroai-lab backup stop
astroai-lab backup restore --yes
```

Env: `ASTROAI_LAB_BACKUP_ENABLED`, `ASTROAI_LAB_BACKUP_INTERVAL` (seconds),
`ASTROAI_LAB_BACKUP_DIR`. Skips when home quota is ≥90% unless `--yes`.

### `astroai-lab ray guide|status`

CANFAR Ray cheat sheet and local manager cluster status.

```bash
astroai-lab ray guide
astroai-lab ray status
astroai-lab --json ray status
canfar create --name raymgr contributed images.canfar.net/astroai/ray-manager:<tag>
```

`/scratch` is session-private (per pod). Share data via `/arc/home` or
`/arc/projects`. See container [RAY.md](https://github.com/astroai/astroai-containers/blob/main/docs/RAY.md).

### `astroai-lab clean home|cache`

Prune caches and home clutter. Pass **`--dry-run`** to preview; destructive runs need explicit category flags (`--all-safe` or individual toggles).

```bash
astroai-lab clean home --all-safe --dry-run
astroai-lab clean cache --all-safe --dry-run
```

### `astroai-lab config show|path`

Optional preferences file.

### `astroai-lab workspace save|restore`

Freeze/restore full project trees (zstd bundles).

### `astroai-lab agent setup|update|sync|sources|project|verify|list|install|models`

AI agent MCP, rules, skills, tool installation, and free model presets.

```bash
astroai-lab agent setup
astroai-lab agent sync              # full refresh: all agents, MCP, skills, GitHub sources
astroai-lab agent update            # alias for sync
astroai-lab agent sources update    # GitHub upstream skills only
astroai-lab agent sources list
astroai-lab agent project
astroai-lab agent install kilo
astroai-lab agent install goose
astroai-lab agent install cline
astroai-lab agent install --list
astroai-lab agent models
astroai-lab agent models free
astroai-lab agent models free --preset long
```


### `astroai-lab kernel`

Jupyter kernels for notebook sessions.

```bash
astroai-lab kernel ensure              # scratch-safe default (no pixi project)
astroai-lab kernel register [PATH]     # project .pixi/.venv as kernel
astroai-lab kernel list
astroai-lab kernel unregister NAME
```

### `astroai-lab notebook starter`

Copy starter notebooks into scratch/work (also shipped at `/opt/astroai/notebooks/` in images).

```bash
astroai-lab notebook starter
astroai-lab notebook starter ray_train --to /scratch
astroai-lab notebook starter marimo          # → TMP_SRC_DIR/notebooks/starter.py
```

### `astroai-lab project init`

Team workspace under `/arc/projects`.

```bash
astroai-lab project init mygroup --members alice,bob
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ASTROAI_LAB_WORK_DIR` | Work directory override |
| `ASTROAI_LAB_SCRATCH_DIR` | Scratch directory override |
| `ASTROAI_LAB_SAVE_DIR` | Env saves directory override |
| `ASTROAI_LAB_PYTHONPATH` | Extra `PYTHONPATH` entries (colon-separated) |
| `TMP_SRC_DIR` | Session work dir (Skaha) |
| `TMP_SCRATCH_DIR` | Session scratch (Skaha) |
| `ASTROAI_LAB_BIN_DIR` | User CLI install dir (default: scratch `.local/bin`) |
| `ASTROAI_LAB_RUNTIME_ROOT` | Runtime uv/pixi roots (default: scratch `.runtime-$USER`) |
| `ASTROAI_LAB_NPM_PREFIX` | npm global prefix (default: scratch `.local`) |
| `ASTROAI_LAB_CONFIG_DIR` | Workbench config (`~/.astroai/lab`) |

Session paths are applied in login shells via `astroai-lab env export` (bundled in `/etc/astroai-lab/profile.sh` on CANFAR images).

See [config.md](config.md) for optional YAML preferences.
