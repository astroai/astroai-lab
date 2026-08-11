# AGENTS.md

AstroAI lab project — guidance for AI coding agents.

**Names:** `canfar` manages platform sessions; `astroai-lab` is the in-session
workbench. AstroAI is the product; CANFAR is the Science Platform.

## Setup (each developer, once)

```bash
astroai-lab agent setup          # on /arc — MCP + skills
astroai-lab agent install kilo   # or goose, cline, opencode, codex, cursor, …
astroai-lab agent install cursor # Cursor Agent CLI onto $SCRATCH
gh auth login
```

Refresh after upgrading lab in-session: `astroai-lab agent update`
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
