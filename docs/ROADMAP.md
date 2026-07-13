# AstroAI Lab roadmap

Workbench CLI for CANFAR sessions. Target users: astrophysicists, ML-aspiring
scientists, and students (astro / CS / stats).

## Principles

- **Two first-class paths:** notebook-only (no pixi required) and project (pixi/uv).
- **Home hygiene:** package caches (pixi/uv/pip/conda/npm/HF/torch) must not land
  under `/arc/home` — redirect to `/scratch` (or intentional `/arc/projects`).
- **Hard rename:** product is `astroai-lab` (no `astroai-lab` alias). Config migrates
  once from `~/.astroai/lab` → `~/.astroai/lab`.
- **No OpenCADC forks:** consume `canfar` and science-platform as-is; work around
  quirks in images + this CLI.
- **No custom Ray UI product:** stock Ray Dashboard + thin scripts/`canfar` launch.

## Layers

| Layer | Repo | Owns |
|-------|------|------|
| Images | `astroai-containers` | Session images, Ray head/workers, profile hooks |
| Workbench | `astroai-lab` | Paths, staging, save/resume, doctor, agents, thin session helpers |
| Contracts | `astroai-workload` | `RunSpec` / Ray Jobs submit — not cluster lifecycle |

## Storage tiers

| Tier | Path | Role |
|------|------|------|
| Fast ephemeral | `/scratch` | Caches, I/O, Ray spill, notebook venvs |
| Code ephemeral | `TMP_SRC_DIR` | Projects, `.pixi`/`.venv` |
| Durable tiny | `/arc/home/$USER` | Auth, MCP, env-save manifests |
| Durable team | `/arc/projects/<group>` | Shared data/results |
| Archive | `vos:` | Long-term anytime |

## Phases

0. Architecture freeze (this doc)
1. Hard rename to `astroai-lab`
2. Home-hygiene guarantee (doctor fail + clean + kernel env)
3. Notebook-first UX + tier helpers + use upstream `canfar` directly
4. Slim Ray (stock dashboard; freeze custom manager UI)
5. Optional `astroai` org migration / CANFAR adoption notes

## Non-goals

- Thin wrappers around `canfar` or `vcp`/`vls` (use those tools directly).

Custom Ray web UI; OpenCADC code changes; pixi-only student path; fat CUDA bases;
growing `astroai-workload` into DAGs.
