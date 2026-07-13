# astroai-lab session guide

## Laptop vs session

- **Laptop / portal:** `canfar login` (or `canfar auth`), `canfar create`, `canfar ps` — start and stop sessions.
- **Inside the session:** `astroai-lab …`, Jupyter, `vcp`/`vls`, pixi/uv.

Notebook students: Portal → **notebook** image → open `/opt/astroai/notebooks/starter.ipynb` (or `astroai-lab notebook starter`) → `astroai-lab kernel ensure` if needed.

Marimo students: Portal → **marimo** image → open seeded `TMP_SRC_DIR/notebooks/starter.py` (or `astroai-lab notebook starter marimo`).

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

## Relationship to `canfar`

| Tool | When to use |
|------|-------------|
| [`canfar`](https://github.com/opencadc/canfar) | Authenticate, create sessions, manage images |
| **`astroai-lab`** | Day-to-day work inside a running session |

## Storage tiers

| Tier | Typical path | Purpose |
|------|--------------|---------|
| Work | `TMP_SRC_DIR` → `/srcdir` | Ephemeral code (fast, session-local) |
| Scratch | `TMP_SCRATCH_DIR` → `/scratch` | Ephemeral data and package download caches |
| Home | `/arc/home` | Persistent config and env saves |
| Projects | `/arc/projects` | Team persistent storage |

Env saves default to **`~/.astroai/lab/saves/`** on persistent home.

## Session loop

```text
1. astroai-lab resume mylab     # or init / clone
2. cd $WORK/mylab && pixi run …
3. … work …
4. astroai-lab save             # anytime; fast lockfile snapshot
5. astroai-lab push             # before closing session
```

Run **`astroai-lab guide`** for a printable cheat sheet.

See **[USAGE.md](USAGE.md)** for examples, CADC/canfar integration, and agents.

## Daily commands

```bash
astroai-lab                       # brief status + next step
astroai-lab init mylab            # new pixi/uv project
astroai-lab clone owner/repo      # gh clone + install
astroai-lab save [name]           # lockfile manifest → /arc
astroai-lab resume NAME           # restore saved env
astroai-lab saves                 # list saved envs (--json)
astroai-lab push --yes              # git push + env save
astroai-lab status --json           # quotas, team projects, GMS/vault, canfar auth/ps
astroai-lab doctor --json           # paths, caches, tools
astroai-lab agent setup             # MCP + skills (once per user on /arc)
astroai-lab agent update            # refresh skills/rules after image upgrade
```

## Platform vs project Python

| Layer | Where | Versions |
|-------|-------|----------|
| Platform CLIs | `/opt/astroai/venv/cadc` | Unpinned at image build; `upgrade-cadc-tools.sh` this session |
| Your project | `TMP_SRC_DIR` pixi/uv env | **Lockfiles** (`pixi.lock`, `uv.lock`) — pin here |

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh --upgrade astroai-lab
```

## Data and hygiene

```bash
astroai-lab data stage SRC [DST]  # /arc → scratch (fast I/O)
astroai-lab data sync SRC DST     # scratch → /arc
astroai-lab clean home --all-safe --dry-run
astroai-lab clean cache --all-safe
```

## Portable OSS projects

Published repos use standard **`pixi.toml`** / **`pyproject.toml`** only.
`astroai-lab clone --from-env` is session-local bootstrap (cache warm + optional lock copy) — nothing lab-specific is committed to git.

## Shell completion

```bash
astroai-lab --install-completion bash   # or zsh, fish
```

## More

- [CLI reference](cli.md)
- [Optional config](config.md)
- [CANFAR docs](https://opencadc.github.io/canfar/)
