# AGENTS.md

CANFAR lab project — guidance for AI coding agents.

## Setup (each developer, once)

```bash
canfar-lab agent setup          # on /arc — MCP + skills + free-model presets
canfar-lab agent install kilo   # or goose, cline, opencode, codex, agent
canfar-lab agent models free    # OpenRouter :free + Kilo auto/free configs
gh auth login
```

Refresh bundles after an image upgrade: `canfar-lab agent sync`

## This repo

```bash
pixi install    # or uv sync — env lives under TMP_SRC_DIR, not $HOME
pixi run …      # or uv run …
canfar-lab push --yes   # before session ends — code on TMP_SRC_DIR is ephemeral
```

Pin Python deps in **pixi.toml / uv.lock** here — not in the image platform venv.
Platform CLIs (`canfar`, `cadcget`, `canfar-lab`) live in `/opt/astroai/venv/cadc`; upgrade this session with `upgrade-cadc-tools.sh` if needed.

Search: `rg`, `fd`, `sg` (ast-grep skill). View files: `peek <path>` (markdown/text/archives) or `bat`/`less`. Help: `canfar-lab guide`, `canfar-lab status --json`.

In webterm, prefer `peek` when pointing the user at generated plans, logs, or archives — do not dump huge files into the chat/terminal raw.
