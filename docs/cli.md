# CLI reference

Global flags (most commands accept these **before** the subcommand, e.g. `canfar-lab --json status`. Several commands also accept the same flags **after** the subcommand name — see examples below):

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable output |
| `--yes` / `-y` | Non-interactive; skip confirmations |
| `--dry-run` | Show actions without executing |
| `--quiet` / `-q` | Minimal output |
| `--version` / `-V` | Show version |

## Top-level commands

### `canfar-lab`

Brief status banner when invoked with no subcommand.

### `canfar-lab init NAME`

Create a pixi or uv project under the work directory.

```bash
canfar-lab init mylab
canfar-lab init mylab --uv --no-git
```

### `canfar-lab clone REPO`

Clone via `gh` and install dependencies.

```bash
canfar-lab clone owner/repo
canfar-lab clone --from-env ml-base owner/repo
```

### `canfar-lab save [NAME]`

Save lockfile manifest to `~/.canfar/lab/saves/`.

```bash
canfar-lab save
canfar-lab save mylab --full
```

### `canfar-lab resume NAME`

Restore a saved environment and run install.

```bash
canfar-lab resume mylab
canfar-lab resume mylab --from /arc/projects/team/env-saves/mylab
```

### `canfar-lab saves`

List saved environments.

```bash
canfar-lab saves
canfar-lab saves --json
```

### `canfar-lab push`

End-of-session: git push (if repo) + env save + summary.

```bash
canfar-lab push
canfar-lab push --yes --name mylab
```

### `canfar-lab status`

Quotas, home breakdown, team project membership, CANFAR auth/sessions, and top processes.

```bash
canfar-lab status
canfar-lab status --json
```

**`--json` keys:** `quotas`, `home`, `processes`, `canfar_auth`, `canfar_sessions`, `arc_project`, `arc_projects`, `gms_groups`, `vault`.

Each **`arc_projects[]`** entry includes `access` (`rw`/`ro`), `acl_groups` (from `getfacl`), `gms_member`, optional nested **`vault`** (VOSpace quota/groups), and `quota` (POSIX `df` on `/arc/projects/<name>`).

**`gms_groups`:** `{groups, source}` from `cadc-groups list` when cert/netrc is available, else `null`.

**`vault`:** `{service, source, auth, nodes[]}` from the vos API (`vault:/<name>`). Vault quotas may also appear in `quotas` as `"<name> (vault)"`.

Requires optional tools on PATH: `getfacl`, `cadc-groups` (CADC venv), `vos` — all ship in AstroAI session images.

### `canfar-lab paths`

Resolved session paths (work, scratch, caches, saves, cwd).

```bash
canfar-lab paths
canfar-lab paths --json
```

### `canfar-lab tools`

Inventory of common session tools on PATH, with versions when available.

```bash
canfar-lab tools
canfar-lab tools --json
```

### `canfar-lab check`

Quick health check: writable work/scratch/save paths plus `git` and `canfar-lab`. Exit code `1` on failure. Use **`--strict`** to also require recommended tools (`pixi`, `uv`, `gh`, `rg`, `jq`, `canfar`).

```bash
canfar-lab check
canfar-lab check --json
canfar-lab check --strict
```

### `canfar-lab doctor`

Full paths and tools report.

```bash
canfar-lab doctor --json
```

### `canfar-lab guide`

Print session workflow cheat sheet.

## Nested commands

### `canfar-lab env save|resume|list`

Backward-compatible aliases for flat commands.

### `canfar-lab data stage|sync`

Stage data from `/arc` to scratch or sync back.

```bash
canfar-lab data stage /arc/home/user/data
canfar-lab data sync /scratch/out /arc/home/user/data
canfar-lab data stage /arc/path --dry-run
canfar-lab data sync /scratch/out /arc/path --yes
```

### `canfar-lab clean home|cache`

Prune caches and home clutter. Pass **`--dry-run`** to preview; destructive runs need explicit category flags (`--all-safe` or individual toggles).

```bash
canfar-lab clean home --all-safe --dry-run
canfar-lab clean cache --all-safe --dry-run
```

### `canfar-lab config show|path`

Optional preferences file.

### `canfar-lab workspace save|restore`

Freeze/restore full project trees (zstd bundles).

### `canfar-lab agent setup|update|sync|sources|project|verify|list|install|models`

AI agent MCP, rules, skills, tool installation, and free model presets.

```bash
canfar-lab agent setup
canfar-lab agent sync              # full refresh: all agents, MCP, skills, GitHub sources
canfar-lab agent update            # alias for sync
canfar-lab agent sources update    # GitHub upstream skills only
canfar-lab agent sources list
canfar-lab agent project
canfar-lab agent install kilo
canfar-lab agent install goose
canfar-lab agent install cline
canfar-lab agent install --list
canfar-lab agent models
canfar-lab agent models free
canfar-lab agent models free --preset long
```

### `canfar-lab project init`

Team workspace under `/arc/projects`.

```bash
canfar-lab project init mygroup --members alice,bob
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `CANFAR_LAB_WORK_DIR` | Work directory override |
| `CANFAR_LAB_SCRATCH_DIR` | Scratch directory override |
| `CANFAR_LAB_SAVE_DIR` | Env saves directory override |
| `CANFAR_LAB_PYTHONPATH` | Extra `PYTHONPATH` entries (colon-separated) |
| `TMP_SRC_DIR` | Session work dir (Skaha) |
| `TMP_SCRATCH_DIR` | Session scratch (Skaha) |
| `CANFAR_LAB_BIN_DIR` | User CLI install dir (default: scratch `.local/bin`) |
| `CANFAR_LAB_RUNTIME_ROOT` | Runtime uv/pixi roots (default: scratch `.runtime-$USER`) |
| `CANFAR_LAB_NPM_PREFIX` | npm global prefix (default: scratch `.local`) |
| `CANFAR_LAB_CONFIG_DIR` | Workbench config (`~/.canfar/lab`) |

Session paths are applied in login shells via `canfar-lab env export` (bundled in `/etc/canfar-lab/profile.sh` on CANFAR images).

See [config.md](config.md) for optional YAML preferences.
