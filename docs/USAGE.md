# canfar-lab usage

**canfar-lab** is the in-session workbench CLI for the
[CANFAR Science Platform](https://www.opencadc.org/canfar/). It complements
[`canfar`](https://github.com/opencadc/canfar) (platform auth and sessions) and
the CADC archive clients (`cadcget`, `cadc-tap`, `vcp`, …) that ship in session
images.

| Doc | Scope |
|-----|--------|
| **USAGE.md** (this file) | `canfar-lab` commands, storage, agents, CADC/canfar integration |
| [guide.md](guide.md) | Short session loop |
| [cli.md](cli.md) | Full CLI reference |
| [config.md](config.md) | Optional `~/.canfar/lab/config.yaml` |

**Session images** (webterm, notebook, vscode, marimo): see
[AstroAI containers USAGE](https://github.com/astroai/containers/blob/main/docs/USAGE.md)
(in-session: `less /opt/astroai/USAGE.md`).

Platform docs: [opencadc.github.io/canfar](https://opencadc.github.io/canfar/)

---

## How the tools fit together

| Tool | Where | Role |
|------|-------|------|
| **`canfar`** | Laptop or inside session | Login, create/list/delete sessions, platform API |
| **CADC clients** | Inside session (image PATH) | Archive data, TAP, VOSpace |
| **`canfar-lab`** | Inside session | Projects, env saves, scratch hygiene, agents |

```bash
# On your laptop — start a session
canfar auth login
canfar create notebook images.canfar.net/astroai/notebook:26.06

# Inside the session — daily work
canfar-lab status
canfar-lab init mylab
cadcget cadc:CFHT/806045o.fits -o "${TMP_SCRATCH_DIR}/"
pixi run python analysis.py
canfar-lab push
```

---

## Install

**In AstroAI session images:** pre-installed in `/opt/astroai/venv/cadc` (on PATH).

**Elsewhere:**

```bash
pip install canfar-lab
# or: uv tool install canfar-lab
```

Shell completion: `canfar-lab --install-completion bash`

---

## First project

```bash
canfar-lab status              # quotas, paths, suggested next step
canfar-lab doctor              # paths, caches, tool availability (--json)
gh auth login                  # once per user — clone/push + GitHub MCP

canfar-lab init mylab
cd mylab && pixi add numpy astropy
pixi run python -c "import astropy; print(astropy.__version__)"
```

Clone existing work:

```bash
canfar-lab clone owner/repo
cd repo && pixi run python analysis.py
```

Save before the session ends (`TMP_SRC_DIR` and `/scratch` are ephemeral):

```bash
git add -A && git commit -m "session work"
canfar-lab push                # git push + env save
```

Resume next time:

```bash
canfar-lab resume mylab
cd mylab && pixi run python analysis.py
```

### Cold start → save → resume loop

Simulates a new session with the same `/arc/home` but empty work dir:

```bash
canfar-lab init mylab && cd mylab
pixi add numpy astropy
canfar-lab env save mylab          # manifest → ~/.canfar/lab/saves/mylab

# Next session (empty TMP_SRC_DIR, same HOME on /arc)
cd "${TMP_SRC_DIR}"
canfar-lab env resume mylab        # restores into ${TMP_SRC_DIR}/mylab
cd mylab && pixi run python analysis.py
```

Integration tests: `pytest tests/integration/test_cold_start_save_resume.py --no-cov`. In AstroAI images: `./scripts/test-canfar-lab-loop.sh` (via `make test-ray`).

Distributed Ray on CANFAR: [AstroAI RAY.md](https://github.com/astroai/containers/blob/main/docs/RAY.md).

---

## Storage (canfar-lab view)

| Tier | Path | Purpose | Backup |
|------|------|---------|--------|
| Work | `TMP_SRC_DIR` → `/srcdir` | Code, active env | **`git push`** |
| Scratch | `TMP_SCRATCH_DIR` → `/scratch` | Data, caches, agent CLIs | `canfar-lab data sync` → `/arc` |
| Home | `~/.canfar/lab` on `/arc/home` | Saves, agent config | automatic |
| Team | `/arc/projects/<group>/` | Shared data, team tools | project quota |

Session shell paths come from **`canfar-lab env export`** (wired in AstroAI images via `/etc/canfar-lab/profile.sh`):

| Variable | Typical value (scratch mounted) |
|----------|--------------------------------|
| `CANFAR_LAB_BIN_DIR` | `${TMP_SCRATCH_DIR}/.local/bin` |
| `CANFAR_LAB_RUNTIME_ROOT` | `${TMP_SCRATCH_DIR}/.runtime-$USER` |
| `UV_CACHE_DIR` | `${TMP_SCRATCH_DIR}/.cache-$USER/uv` |

Inspect: **`canfar-lab doctor`**.

```bash
canfar-lab data stage /arc/projects/mygroup/catalog.fits
canfar-lab data sync "${TMP_SCRATCH_DIR}/results/" /arc/projects/mygroup/results/
canfar-lab clean home --all-safe --dry-run
canfar-lab clean cache --all-safe
```

---

## Working with `canfar` and CADC clients

**canfar-lab does not replace `canfar`.** Use `canfar` for platform operations; use CADC CLIs for archive I/O; use `canfar-lab` for project and session hygiene.

### CADC clients (in session images)

| CLI | Package | Example |
|-----|---------|---------|
| `cadcget`, `cadcput` | cadcdata | `cadcget cadc:CFHT/806045o.fits "${TMP_SCRATCH_DIR}/"` |
| `cadc-tap` | cadctap | `cadc-tap "SELECT * FROM caom2.Observation LIMIT 5"` |
| `vcp`, `vls` | vos | `vls vos:/` |
| `canfar` | canfar | `canfar sessions list` |

Auth:

```bash
canfar auth login              # Science Platform
cadc-get-cert -u "$USER"       # X509 for vos/cadcdata when needed
```

In project code, pin versions in pixi/uv:

```bash
pixi add cadcdata cadctap vos canfar
```

`canfar-lab doctor` reports whether `canfar`, `cadcget`, `pixi`, and `uv` are available.

---

## Command reference

| Command | Purpose |
|---------|---------|
| `canfar-lab` | Brief status |
| `canfar-lab guide` | Printable cheat sheet |
| `canfar-lab status` | Quotas, space, processes |
| `canfar-lab doctor [--json]` | Paths, caches, tools |
| `canfar-lab init NAME` | New pixi/uv project |
| `canfar-lab clone REPO` | `gh` clone + install |
| `canfar-lab save [NAME]` | Lockfile manifest → `~/.canfar/lab/saves/` |
| `canfar-lab resume NAME` | Restore saved env |
| `canfar-lab saves` | List saves (`--json`) |
| `canfar-lab push` | Git push + env save |
| `canfar-lab env export` | Bash `export` lines for shells |
| `canfar-lab env install-shell DEST` | Install profile/hooks (image maintainers) |
| `canfar-lab agent setup` | MCP + skills (once per user) |
| `canfar-lab agent install TOOL` | AI CLI → `$CANFAR_LAB_BIN_DIR` |
| `canfar-lab agent models free` | Free-tier model presets |

Add **`--json`** for scripts; **`--yes`** to skip prompts.

Full flag lists: [cli.md](cli.md).

---

## AI coding agents

```bash
canfar-lab agent setup
canfar-lab agent install kilo    # or goose, cline, opencode, codex, agent
canfar-lab agent models free
canfar-lab agent update          # after image upgrade
```

Installs go to **`$CANFAR_LAB_BIN_DIR`** (scratch when mounted, not `$HOME`).

List tools: `canfar-lab agent install --list`

---

## Examples

**Shared ML env across clones:**

```bash
canfar-lab init ml-base && cd ml-base
pixi add torch numpy
canfar-lab save ml-base
canfar-lab clone --from-env ml-base owner/project-a
```

**Non-interactive push (hooks / CI inside session):**

```bash
canfar-lab --yes push
# or: canfar-lab push --yes
```

**Scriptable diagnostics:**

```bash
canfar-lab doctor --json | jq .tools
canfar-lab status --json
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Lost code | `git push` or `canfar-lab push` before closing |
| `cadcget` auth | `cadc-get-cert -u $USER` |
| Home quota full | `canfar-lab clean home --all-safe` |
| Caches on `/arc/home` | `canfar-lab doctor` — should show scratch paths when mounted |
| Agent missing | `echo $CANFAR_LAB_BIN_DIR`; new shell or `hash -r` |

---

## See also

- [CANFAR platform docs](https://opencadc.github.io/canfar/)
- [AstroAI session guide](https://github.com/astroai/containers/blob/main/docs/USAGE.md) — images, GPU, CVMFS, portal
