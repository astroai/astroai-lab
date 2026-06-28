---
name: canfar-lab-workflow
description: >-
  CANFAR CANFAR lab quick reference — setup, pixi/uv, storage, canfar-lab-* commands.
  Use for new users or session workflow questions on CANFAR lab.
---
# CANFAR lab in 3 commands

```bash
canfar-lab agent setup              # once per user — MCP + skills (persists on /arc)
canfar-lab agent install agent            # or: claude, goose, opencode, codex
gh auth login                    # GitHub for gh + GitHub MCP
```

Refresh after image upgrade: `canfar-lab agent setup update`

## Daily workflow

```bash
canfar-lab init mylab                # or canfar-lab clone owner/repo
canfar-lab clone --from-env ml-base owner/repo   # warm caches from saved stack
cd "${TMP_SRC_DIR}/mylab"
pixi install                     # or uv sync
pixi run python analysis.py
git push                         # before session ends!
```

## Storage (memorize this)

| Path | What |
|------|------|
| `${TMP_SRC_DIR}` | Code + `.pixi`/`.venv` — **gone when session ends** |
| `${TMP_SCRATCH_DIR}` | Big data + download caches |
| `/arc` (`$HOME`) | Agent config, saves, `~/.local/bin` |

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
canfar-lab-debug                    # paths, caches, uv python dir
canfar-lab clean home --all-safe    # when /arc quota is tight
less /opt/canfar-lab/USAGE.md
```
