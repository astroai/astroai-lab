---
name: astroai-lab-workflow
description: >-
  AstroAI lab quick reference — setup, pixi/uv, storage, astroai-lab commands.
  Use for new users or session workflow questions on AstroAI lab.
---
# AstroAI lab in 3 commands

```bash
astroai-lab agent setup              # once per user — MCP + skills (persists on /arc)
astroai-lab agent install kilo       # or: goose, cline, opencode, codex, agent
astroai-lab agent models free        # OpenRouter + Kilo free-tier model presets
gh auth login                       # GitHub for gh + GitHub MCP
```

Refresh agent bundles after an image upgrade: `astroai-lab agent sync`
GitHub upstream skills only: `astroai-lab agent sources update`

## Daily workflow

```bash
astroai-lab init mylab                # or astroai-lab clone owner/repo
astroai-lab clone --from-env ml-base owner/repo   # warm caches from saved stack
cd "${TMP_SRC_DIR}/mylab"
pixi install                     # or uv sync
pixi run python analysis.py
astroai-lab push --yes            # before session ends (or: astroai-lab --yes push)
```

Global flags (`--json`, `--yes`, `--dry-run`) work **before or after** the subcommand:
`astroai-lab status --json`, `astroai-lab clean home --dry-run`, `astroai-lab saves --json`.

## Storage (memorize this)

| Path | What |
|------|------|
| `${TMP_SRC_DIR}` | Code + project `.pixi`/`.venv` — **ephemeral** |
| `${TMP_SCRATCH_DIR}` | Data, download caches, runtime installs (`ASTROAI_LAB_BIN_DIR`, uv/pixi roots) |
| `/opt/astroai/venv/cadc` | Platform CLIs: `canfar`, `cadcget`, `astroai-lab` — **writable this session** |
| `/arc/projects/<team>/.local` | Shared team tools + env saves (persistent) |
| `/arc` (`$HOME`) | **Small only** — agent MCP config, gh auth, lockfile saves (`~/.astroai/lab`) |

**Project deps:** use pixi/uv lockfiles under `${TMP_SRC_DIR}` — that is where versions belong.
**Platform CLIs:** image installs are unpinned; bump in-session with `upgrade-cadc-tools.sh` (lost when the session ends).

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh 'astroai-lab @ git+https://github.com/sfabbro/canfar-lab.git@main'
astroai-lab data stage /arc/path --dry-run
astroai-lab doctor --json
```

Avoid pip/uv/pixi/conda/npm **project** installs under `$HOME` — use project envs in `${TMP_SRC_DIR}` or team paths on `/arc/projects`.

Optional: `${TMP_SRC_DIR}/.astroai-lab/pythonpath` or `ASTROAI_LAB_PYTHONPATH` for extra import paths.

## Search & run (standard tools — no custom commands)

```bash
rg 'pattern' --type py
fd name
sg -p 'class $N' -l py          # needs: astroai-lab agent install ast-grep
pixi run pytest -q
uv run python script.py
peek README.md                  # markdown/text; peek archive.tgz [member]
```

When showing the user a generated markdown, log, or archive in webterm (or any AstroAI session), prefer `peek <path>` (or `bat`/`less`) over dumping huge files raw.

## Help

```bash
astroai-lab guide
astroai-lab status --json          # quotas, team projects (access/ACL/GMS/vault), canfar auth/ps
astroai-lab paths --json           # resolved work/scratch/cache/save paths
astroai-lab tools --json           # tools on PATH (+ versions)
astroai-lab check                  # quick health check
astroai-lab doctor --json          # full paths, caches, tools on PATH
astroai-lab clean home --all-safe --dry-run
less /opt/astroai/USAGE.md
```
