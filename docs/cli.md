# CLI reference

Global flags (all commands):

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

Quotas, home breakdown, top CPU processes.

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
```

### `canfar-lab clean home|cache`

Prune caches and home clutter (defaults to dry-run on destructive ops).

```bash
canfar-lab clean home --all-safe --dry-run
canfar-lab clean cache --all-safe --yes
```

### `canfar-lab config show|path`

Optional preferences file.

### `canfar-lab workspace save|restore`

Freeze/restore full project trees (zstd bundles).

### `canfar-lab agent setup|update|project|verify|list|install|models`

AI agent MCP, rules, skills, tool installation, and free model presets.

```bash
canfar-lab agent setup
canfar-lab agent update
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
| `CANFAR_LAB_NPM_PREFIX` | npm global prefix (default: scratch `.local`) |
| `CANFAR_LAB_CONFIG_DIR` | Workbench config (`~/.canfar/lab`) |

Session paths are applied in login shells via `canfar-lab env export` (bundled in `/etc/canfar-lab/profile.sh` on CANFAR images).

See [config.md](config.md) for optional YAML preferences.
