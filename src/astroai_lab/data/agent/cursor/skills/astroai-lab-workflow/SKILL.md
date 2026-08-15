---
name: astroai-lab-workflow
description: >-
  AstroAI lab quick reference — setup, pixi/uv, storage, astroai-lab commands.
  Use for new users or session workflow questions on AstroAI lab.
---
# AstroAI lab in 3 commands

**Names:** `canfar` = platform sessions/auth; `astroai-lab` = in-session workbench;
AstroAI = product images/tools; CANFAR = Science Platform host.

```bash
astroai-lab agent setup              # once per user — MCP + skills (persists on /arc)
astroai-lab agent install kilo       # or: goose, cline, opencode, codex, cursor, …
astroai-lab agent install cursor     # Cursor Agent CLI onto $SCRATCH
gh auth login                       # GitHub for gh + GitHub MCP
```

Discover what’s available: `astroai-lab agent list` · plugins: `astroai-lab agent plugins list`  
Plugins: `astroai-lab agent plugins install ponytail`  
Refresh after upgrading lab in-session: `astroai-lab agent update`  
Broken agent configs (esp. OpenCode JSON): `astroai-lab agent verify` · `astroai-lab agent verify --fix`

## Daily workflow

```bash
astroai-lab init mylab                # or astroai-lab clone owner/repo
astroai-lab clone --from-env ml-base owner/repo   # warm caches from saved stack
cd "${WORK}/mylab"
pixi install                     # or uv sync
pixi run python analysis.py
astroai-lab save                  # snapshot env before session ends
astroai-lab save mylab --to /arc/projects/<team>/env-saves/mylab
```

Global flags (`--json`, `--yes`, `--dry-run`) work **before or after** the subcommand:
`astroai-lab status --json`, `astroai-lab saves --json`.

## Storage (memorize this)

| Path | What |
|------|------|
| `${WORK}` | Code + project `.pixi`/`.venv` — ephemeral (on CANFAR: `$SCRATCH/src`, survives container OOM) |
| `${SCRATCH}` | Data, download caches, runtime installs (`ASTROAI_LAB_BIN_DIR`, uv/pixi roots) |
| `/opt/astroai/venv/cadc` | Platform CLIs: `canfar`, `cadcget`, `astroai-lab` — **writable this session** |
| `/arc/projects/<team>/.local` | Shared team tools (persistent) |
| `/arc` (`$HOME`) | **Small only** — agent MCP config, gh auth, lockfile saves (`~/.astroai/lab`) |

**Project deps:** use pixi/uv lockfiles under `${WORK}` — that is where versions belong.
**Platform CLIs:** image installs are unpinned; bump in-session with `upgrade-cadc-tools.sh` (lost when the session ends).

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh 'astroai-lab @ git+https://github.com/astroai/astroai-lab.git@main'
astroai-lab status --json
```

Avoid pip/uv/pixi/conda/npm **project** installs under `$HOME` — use project envs in `${WORK}` or team paths on `/arc/projects`.

Optional: `${WORK}/.astroai-lab/pythonpath` or `ASTROAI_LAB_PYTHONPATH` for extra import paths.

## Search & run (standard tools — no custom commands)

```bash
rg 'pattern' --type py
fd name
sg -p 'class $N' -l py          # needs: astroai-lab agent plugins install ast-grep-cli
pixi run pytest -q
uv run python script.py
peek README.md                  # markdown/text; peek archive.tgz [member]
```

When showing the user a generated markdown, log, or archive in webterm (or any AstroAI session), prefer `peek <path>` (or `bat`/`less`) over dumping huge files raw.

## Help

```bash
astroai-lab help
astroai-lab status --json          # quotas, team projects (access/ACL/GMS/vault), canfar auth/ps
astroai-lab saves --json           # saved environments
astroai-lab agent list             # agent CLIs, config bundles, skills
astroai-lab agent verify           # configs present + parseable
less /opt/astroai/USAGE.md
```
