# AGENTS.md

AstroAI lab project — guidance for AI coding agents.

## Setup (each developer, once)

```bash
astroai-lab agent setup          # on /arc — MCP + skills + free-model presets
astroai-lab agent install kilo   # or goose, cline, opencode, codex, agent
astroai-lab agent models free    # OpenRouter :free + Kilo auto/free configs
gh auth login
```

Refresh bundles after an image upgrade: `astroai-lab agent sync`

## This repo

```bash
pixi install    # or uv sync — env lives under TMP_SRC_DIR, not $HOME
pixi run …      # or uv run …
astroai-lab push --yes   # before session ends — code on TMP_SRC_DIR is ephemeral
```

Pin Python deps in **pixi.toml / uv.lock** here — not in the image platform venv.
Platform CLIs (`canfar`, `cadcget`, `astroai-lab`) live in `/opt/astroai/venv/cadc`; upgrade this session with `upgrade-cadc-tools.sh` if needed.

Search: `rg`, `fd`, `sg` (ast-grep skill). View files: `peek <path>` (markdown/text/archives) or `bat`/`less`. Help: `astroai-lab guide`, `astroai-lab status --json`, `astroai-lab paths`, `astroai-lab tools`, `astroai-lab check`.

In webterm, prefer `peek` when pointing the user at generated plans, logs, or archives — do not dump huge files into the chat/terminal raw.
