# AGENTS.md

CANFAR lab project — guidance for AI coding agents.

## Setup (each developer, once)

```bash
canfar-lab agent setup          # on /arc — MCP + skills + free-model presets
canfar-lab agent install kilo   # or goose, cline, opencode, codex, agent
canfar-lab agent models free    # OpenRouter :free + Kilo auto/free configs
gh auth login
```

Refresh: `canfar-lab agent update`

## This repo

```bash
pixi install    # or uv sync
pixi run …      # or uv run …
canfar-lab --yes push   # before session ends — code on TMP_SRC_DIR is ephemeral
```

Search: `rg`, `fd`, `sg` (ast-grep skill). Help: `canfar-lab guide`, `canfar-lab status`.
