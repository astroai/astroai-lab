# AGENTS.md

AstroAI lab project — guidance for AI coding agents.

**Names:** `canfar` manages platform sessions; `astroai-lab` is the in-session
workbench. AstroAI is the product; CANFAR is the Science Platform.

## Setup (each developer, once)

```bash
astroai-lab agent setup          # on /arc — MCP + skills + free-model presets
astroai-lab agent install kilo   # or goose, cline, opencode, codex, qoder, agent
astroai-lab agent models free    # OpenRouter :free + Kilo auto/free configs
gh auth login
```

Refresh bundles after an image upgrade: `astroai-lab agent update`
Overview / broken configs: `astroai-lab agent list` · `astroai-lab agent verify`
Curated lean/science plugins: `astroai-lab agent plugins list` · `astroai-lab agent plugins install ponytail`

## This repo

```bash
pixi install    # or uv sync — env lives under $WORK, not $HOME
pixi run …      # or uv run …
astroai-lab save         # before session ends — code on $WORK is ephemeral
```

Pin Python deps in **pixi.toml / uv.lock** here — not in the image platform venv.
Platform CLIs (`canfar`, `cadcget`, `astroai-lab`) live in `/opt/astroai/venv/cadc`; upgrade this session with `upgrade-cadc-tools.sh` if needed.

Search: `rg`, `fd`, `sg` (ast-grep skill). View files: `peek <path>` (markdown/text/archives) or `bat`/`less`. Help: `astroai-lab help`, `astroai-lab status --json`.

In webterm, prefer `peek` when pointing the user at generated plans, logs, or archives.
