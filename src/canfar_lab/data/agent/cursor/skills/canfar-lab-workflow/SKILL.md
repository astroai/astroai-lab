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

Refresh after image upgrade: `canfar-lab agent update`

## Daily workflow

```bash
canfar-lab init mylab                # or canfar-lab clone owner/repo
canfar-lab clone --from-env ml-base owner/repo   # warm caches from saved stack
cd "${TMP_SRC_DIR}/mylab"
pixi install                     # or uv sync
pixi run python analysis.py
canfar-lab --yes push            # before session ends!
```

## Storage (memorize this)

| Path | What |
|------|------|
| `${TMP_SRC_DIR}` | Code + project `.pixi`/`.venv` — **ephemeral** |
| `${TMP_SCRATCH_DIR}` | Data, download caches, runtime installs (`CANFAR_LAB_BIN_DIR`, uv/pixi roots) |
| `/arc/projects/<team>/.local` | Shared team tools + env saves (persistent) |
| `/arc` (`$HOME`) | **Small only** — agent MCP config, gh auth, lockfile saves |

**Avoid** pip/uv/pixi/conda/npm installs under `$HOME` — use project envs in `${TMP_SRC_DIR}` or team paths on `/arc/projects`.

Optional: `${TMP_SRC_DIR}/.canfar-lab/pythonpath` or `CANFAR_LAB_PYTHONPATH` for extra import paths.

```bash
canfar-lab doctor   # shows user_bin, npm_prefix, runtime_root, caches
```

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
canfar-lab status                   # quotas, home/project space
canfar-lab doctor                   # paths, caches, uv python dir
canfar-lab clean home --all-safe    # when /arc quota is tight
less /opt/astroai/USAGE.md
```
