# canfar-lab session guide

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

## Relationship to `canfar`

| Tool | When to use |
|------|-------------|
| [`canfar`](https://github.com/opencadc/canfar) | Authenticate, create sessions, manage images |
| **`canfar-lab`** | Day-to-day work inside a running session |

## Storage tiers

| Tier | Typical path | Purpose |
|------|--------------|---------|
| Work | `TMP_SRC_DIR` → `/srcdir` | Ephemeral code (fast, session-local) |
| Scratch | `TMP_SCRATCH_DIR` → `/scratch` | Ephemeral data and package download caches |
| Home | `/arc/home` | Persistent config and env saves |
| Projects | `/arc/projects` | Team persistent storage |

Env saves default to **`~/.canfar/lab/saves/`** on persistent home.

## Session loop

```text
1. canfar-lab resume mylab     # or init / clone
2. cd $WORK/mylab && pixi run …
3. … work …
4. canfar-lab save             # anytime; fast lockfile snapshot
5. canfar-lab push             # before closing session
```

Run **`canfar-lab guide`** for a printable cheat sheet.

See **[USAGE.md](USAGE.md)** for examples, CADC/canfar integration, and agents.

## Daily commands

```bash
canfar-lab                       # brief status + next step
canfar-lab init mylab            # new pixi/uv project
canfar-lab clone owner/repo      # gh clone + install
canfar-lab save [name]           # lockfile manifest → /arc
canfar-lab resume NAME           # restore saved env
canfar-lab saves                 # list saved envs (--json)
canfar-lab push --yes              # git push + env save
canfar-lab status --json           # quotas, canfar auth/ps
canfar-lab doctor --json           # paths, caches, tools
canfar-lab agent setup             # MCP + skills (once per user on /arc)
canfar-lab agent update            # refresh skills/rules after image upgrade
```

## Platform vs project Python

| Layer | Where | Versions |
|-------|-------|----------|
| Platform CLIs | `/opt/astroai/venv/cadc` | Unpinned at image build; `upgrade-cadc-tools.sh` this session |
| Your project | `TMP_SRC_DIR` pixi/uv env | **Lockfiles** (`pixi.lock`, `uv.lock`) — pin here |

```bash
upgrade-cadc-tools.sh list
upgrade-cadc-tools.sh --upgrade canfar-lab
```

## Data and hygiene

```bash
canfar-lab data stage SRC [DST]  # /arc → scratch (fast I/O)
canfar-lab data sync SRC DST     # scratch → /arc
canfar-lab clean home --all-safe --dry-run
canfar-lab clean cache --all-safe
```

## Portable OSS projects

Published repos use standard **`pixi.toml`** / **`pyproject.toml`** only.
`canfar-lab clone --from-env` is session-local bootstrap (cache warm + optional lock copy) — nothing lab-specific is committed to git.

## Shell completion

```bash
canfar-lab --install-completion bash   # or zsh, fish
```

## More

- [CLI reference](cli.md)
- [Optional config](config.md)
- [CANFAR docs](https://opencadc.github.io/canfar/)
