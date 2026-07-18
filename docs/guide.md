# Session guide

Short cheat sheet for work **inside** an AstroAI session on CANFAR.

## Who does what

```mermaid
flowchart LR
  subgraph outside [Outside the session]
    Login["canfar login"]
    Create["canfar create / Science Portal"]
  end
  subgraph inside [Inside the session]
    Lab["astroai-lab"]
    Work["pixi / uv / notebooks / CADC tools"]
  end
  Login --> Create --> inside
  Lab --> Work
```

| Tool | Use it for |
|------|------------|
| [`canfar`](https://github.com/opencadc/canfar) | Authenticate, create and list sessions, manage images |
| **`astroai-lab`** | Projects, env save/resume, paths, data stage/sync, doctor, agents |
| CADC clients (`cadcget`, `vcp`, …) | Archive and VOSpace I/O (shipped in session images) |

Notebook path: Science Portal → **notebook** image →
`/opt/astroai/notebooks/starter.ipynb` (or `astroai-lab notebook starter`) →
`astroai-lab kernel ensure` if the kernel is missing.

Marimo path: Science Portal → **marimo** image →
`TMP_SRC_DIR/notebooks/starter.py` opens by default
(or `astroai-lab notebook starter marimo`).

## Storage tiers

| Tier | Typical path | Purpose |
|------|--------------|---------|
| Work | `TMP_SRC_DIR` → `/srcdir` | Ephemeral code (fast, session-local) |
| Scratch | `TMP_SCRATCH_DIR` → `/scratch` | Ephemeral data and package caches |
| Home | `/arc/home` | Persistent config and env saves |
| Projects | `/arc/projects` | Team persistent storage |

Env saves default to **`~/.astroai/lab/saves/`** on persistent home.

## Session loop

```text
1. astroai-lab resume mylab     # or init / clone
2. cd $WORK/mylab && pixi run …
3. … work …
4. astroai-lab save             # anytime; lockfile snapshot
5. astroai-lab push             # before closing session
```

Same text from the CLI: **`astroai-lab guide`**.

## Daily commands

```bash
astroai-lab                       # brief status + next step
astroai-lab init mylab
astroai-lab clone owner/repo
astroai-lab save [name]
astroai-lab resume NAME
astroai-lab saves
astroai-lab push --yes
astroai-lab status --json
astroai-lab doctor --json
astroai-lab agent setup
astroai-lab agent update
```

## Platform vs project Python

| Layer | Where | How it is versioned |
|-------|-------|---------------------|
| Platform CLIs | `/opt/astroai/venv/cadc` | Image build + optional `upgrade-cadc-tools.sh` this session |
| Your project | `TMP_SRC_DIR` pixi/uv env | Lockfiles (`pixi.lock`, `uv.lock`) |

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh --upgrade astroai-lab
```

## Data and hygiene

```bash
astroai-lab data stage SRC [DST]   # /arc → scratch
astroai-lab data sync SRC DST      # scratch → /arc
astroai-lab clean home --all-safe --dry-run
astroai-lab clean cache --all-safe
```

## Portable projects

Published repos use standard **`pixi.toml`** / **`pyproject.toml`** only.
`astroai-lab clone --from-env` is session-local bootstrap (cache warm / optional
lock copy) — lab-specific state is not committed to git.

## Shell completion

```bash
astroai-lab --install-completion bash   # or zsh, fish
```

## More

- [USAGE.md](USAGE.md) — full narrative
- [cli.md](cli.md) — flag and command reference
- [config.md](config.md) — optional preferences
- [CANFAR docs](https://opencadc.github.io/canfar/)
