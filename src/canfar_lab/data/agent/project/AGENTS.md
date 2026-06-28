# AGENTS.md

CANFAR CANFAR lab project — guidance for AI coding agents.

## Setup (each developer, once)

```bash
canfar-lab agent setup          # on /arc — MCP + skills
canfar-lab agent install agent        # or claude, goose, opencode, codex
gh auth login
```

Refresh: `canfar-lab agent setup update`

## This repo

```bash
pixi install    # or uv sync
pixi run …      # or uv run …
git push        # before session ends — code on TMP_SRC_DIR is ephemeral
```

Search: `rg`, `fd`, `sg` (ast-grep skill). Help: `canfar-lab guide`, `canfar-lab status`.
