---
name: canfar-lab-workflow
description: >-
  CANFAR lab quick reference — setup, pixi/uv, storage, canfar-lab commands.
  Use for new users or session workflow questions on CANFAR lab.
---
# CANFAR lab in 3 commands

```bash
canfar-lab agent setup              # once per user — MCP + skills (persists on /arc)
canfar-lab agent install kilo       # or: goose, cline, opencode, codex, agent
canfar-lab agent models free        # OpenRouter + Kilo free-tier model presets
gh auth login                       # GitHub for gh + GitHub MCP
```

Refresh agent bundles after an image upgrade: `canfar-lab agent sync`
GitHub upstream skills only: `canfar-lab agent sources update`

## Daily workflow

```bash
canfar-lab init mylab                # or canfar-lab clone owner/repo
canfar-lab clone --from-env ml-base owner/repo   # warm caches from saved stack
cd "${TMP_SRC_DIR}/mylab"
pixi install                     # or uv sync
pixi run python analysis.py
canfar-lab push --yes            # before session ends (or: canfar-lab --yes push)
```

Global flags (`--json`, `--yes`, `--dry-run`) work **before or after** the subcommand:
`canfar-lab status --json`, `canfar-lab clean home --dry-run`, `canfar-lab saves --json`.

## Storage (memorize this)

| Path | What |
|------|------|
| `${TMP_SRC_DIR}` | Code + project `.pixi`/`.venv` — **ephemeral** |
| `${TMP_SCRATCH_DIR}` | Data, download caches, runtime installs (`CANFAR_LAB_BIN_DIR`, uv/pixi roots) |
| `/opt/astroai/venv/cadc` | Platform CLIs: `canfar`, `cadcget`, `canfar-lab` — **writable this session** |
| `/arc/projects/<team>/.local` | Shared team tools + env saves (persistent) |
| `/arc` (`$HOME`) | **Small only** — agent MCP config, gh auth, lockfile saves (`~/.canfar/lab`) |

**Project deps:** use pixi/uv lockfiles under `${TMP_SRC_DIR}` — that is where versions belong.
**Platform CLIs:** image installs are unpinned; bump in-session with `upgrade-cadc-tools.sh` (lost when the session ends).

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh 'canfar-lab @ git+https://github.com/sfabbro/canfar-lab.git@main'
canfar-lab data stage /arc/path --dry-run
canfar-lab doctor --json
```

Avoid pip/uv/pixi/conda/npm **project** installs under `$HOME` — use project envs in `${TMP_SRC_DIR}` or team paths on `/arc/projects`.

Optional: `${TMP_SRC_DIR}/.canfar-lab/pythonpath` or `CANFAR_LAB_PYTHONPATH` for extra import paths.

## Search & run (standard tools — no custom commands)

```bash
rg 'pattern' --type py
fd name
sg -p 'class $N' -l py          # needs: canfar-lab agent install ast-grep
pixi run pytest -q
uv run python script.py
```

## Help

```bash
canfar-lab guide
canfar-lab status --json          # quotas, team projects (access/ACL/GMS/vault), canfar auth/ps
canfar-lab doctor --json          # paths, caches, tools on PATH
canfar-lab clean home --all-safe --dry-run
less /opt/astroai/USAGE.md
```
