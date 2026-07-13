# astroai-lab usage

**astroai-lab** is the in-session workbench CLI for the
[CANFAR Science Platform](https://www.opencadc.org/canfar/). It complements
[`canfar`](https://github.com/opencadc/canfar) (platform auth and sessions) and
the CADC archive clients (`cadcget`, `cadc-tap`, `vcp`, …) that ship in session
images.

| Doc | Scope |
|-----|--------|
| **USAGE.md** (this file) | `astroai-lab` commands, storage, agents, CADC/canfar integration |
| [guide.md](guide.md) | Short session loop |
| [cli.md](cli.md) | Full CLI reference |
| [config.md](config.md) | Optional `~/.astroai/lab/config.yaml` |

**Session images** (webterm, notebook, vscode, marimo): see
[AstroAI containers USAGE](https://github.com/astroai/astroai-containers/blob/main/docs/USAGE.md)
(in-session: `less /opt/astroai/USAGE.md`).

Platform docs: [opencadc.github.io/canfar](https://opencadc.github.io/canfar/)

---

## Where you work (laptop vs session)

| Where | What you do | Tools |
|-------|-------------|--------|
| **Laptop / browser** | Log in, start/stop sessions | Science Portal, or `canfar auth` / `canfar create` / `canfar ps` |
| **Inside a CANFAR session** | Analyze data, notebooks, training, agents | `astroai-lab`, Jupyter, `vcp`/`vls`, pixi/uv |

**`astroai-lab` is an in-session tool.** Students do not run `kernel ensure` or
`doctor` on their laptop — those commands run in the session terminal / notebook
after the portal has launched an AstroAI image.

### Student path (notebook-first) — all steps inside the session

1. **Laptop:** open the Science Portal → launch **notebook** (GPU node only if you need a GPU).
2. **In the session:** open `/opt/astroai/notebooks/starter.ipynb` (or `astroai-lab notebook starter`).
3. **In the session:** use the **AstroAI** kernel; if missing, terminal: `astroai-lab kernel ensure`.
4. **In the session:** `astroai-lab doctor` — caches should sit under `/scratch`, not `$HOME`.
5. **In the session:** work on `/scratch`; keep results with `astroai-lab data sync … /arc/projects/…` or plain `vcp` to `vos:`.
6. Later projects: still **in session**, `astroai-lab init` / `clone` + pixi/uv.

VOSpace: use **`vls` / `vcp`** from the image (vostools). No `astroai-lab` wrapper.

## How the tools fit together

| Tool | Where | Role |
|------|-------|------|
| **`canfar`** | Laptop or session | Login, create/list/delete sessions |
| **`vcp` / `vls`** | Session (image PATH) | VOSpace archive |
| **`astroai-lab`** | **Session only** | Paths, hygiene, env saves, kernels, agents, `/arc`↔`/scratch` rsync |

```bash
# On your laptop — start a session
canfar auth login
canfar create notebook images.canfar.net/astroai/notebook:26.06

# Inside the session — daily work
astroai-lab status
astroai-lab init mylab
cadcget cadc:CFHT/806045o.fits -o "${TMP_SCRATCH_DIR}/"
pixi run python analysis.py
astroai-lab push
```

---

## Install

**In AstroAI session images:** pre-installed in `/opt/astroai/venv/cadc` (on PATH).

**Elsewhere:**

```bash
pip install astroai-lab
# or: uv tool install astroai-lab
```

Shell completion: `astroai-lab --install-completion bash`

---

## First project

```bash
astroai-lab                        # brief banner + next step (not full status)
astroai-lab status                 # quotas, team projects, GMS/vault, processes
astroai-lab paths                  # resolved work/scratch/cache/save paths
astroai-lab tools                  # tools on PATH (+ versions)
astroai-lab check                  # quick health check (exit 1 on failure)
astroai-lab doctor                 # full paths, caches, tool availability (--json)
gh auth login                  # once per user — clone/push + GitHub MCP

astroai-lab init mylab
cd mylab && pixi add numpy astropy
pixi run python -c "import astropy; print(astropy.__version__)"
```

Clone existing work:

```bash
astroai-lab clone owner/repo
cd repo && pixi run python analysis.py
```

Save before the session ends (`TMP_SRC_DIR` and `/scratch` are ephemeral):

```bash
git add -A && git commit -m "session work"
astroai-lab push                # git push + env save
```

Resume next time:

```bash
astroai-lab resume mylab
cd mylab && pixi run python analysis.py
```

### Cold start → save → resume loop

Simulates a new session with the same `/arc/home` but empty work dir:

```bash
astroai-lab init mylab && cd mylab
pixi add numpy astropy
astroai-lab env save mylab          # manifest → ~/.astroai/lab/saves/mylab

# Next session (empty TMP_SRC_DIR, same HOME on /arc)
cd "${TMP_SRC_DIR}"
astroai-lab env resume mylab        # restores into ${TMP_SRC_DIR}/mylab
cd mylab && pixi run python analysis.py
```

Integration tests: `pytest tests/integration/test_cold_start_save_resume.py --no-cov`. In AstroAI images: [containers/scripts/test-astroai-lab-loop.sh](https://github.com/astroai/astroai-containers/blob/main/scripts/test-astroai-lab-loop.sh) (`make test-ray BUILD_TAG=local` in the containers repo).

Distributed Ray on CANFAR: [AstroAI RAY.md](https://github.com/astroai/astroai-containers/blob/main/docs/RAY.md).

---

## Storage (astroai-lab view)

| Tier | Path | Purpose | Backup |
|------|------|---------|--------|
| Work | `TMP_SRC_DIR` → `/srcdir` | Code, active env | **`git push`** |
| Scratch | `TMP_SCRATCH_DIR` → `/scratch` | Data, caches, agent CLIs | `astroai-lab data sync` → `/arc` |
| Home | `~/.astroai/lab` on `/arc/home` | Saves, agent config | automatic |
| Team | `/arc/projects/<group>/` | Shared data, team tools | project quota |

Session shell paths come from **`astroai-lab env export`** (wired in AstroAI images via `/etc/astroai-lab/profile.sh`):

| Variable | Typical value (scratch mounted) |
|----------|--------------------------------|
| `ASTROAI_LAB_BIN_DIR` | `${TMP_SCRATCH_DIR}/.local/bin` |
| `ASTROAI_LAB_RUNTIME_ROOT` | `${TMP_SCRATCH_DIR}/.runtime-$USER` |
| `UV_CACHE_DIR` | `${TMP_SCRATCH_DIR}/.cache-$USER/uv` |

Inspect: **`astroai-lab doctor`**.

```bash
astroai-lab data stage /arc/projects/mygroup/catalog.fits
astroai-lab data sync "${TMP_SCRATCH_DIR}/results/" /arc/projects/mygroup/results/
astroai-lab clean home --all-safe --dry-run
astroai-lab clean cache --all-safe
```

---

## Working with `canfar` and CADC clients

**astroai-lab does not replace `canfar`.** Use `canfar` for platform operations; use CADC CLIs for archive I/O; use `astroai-lab` for project and session hygiene.

### CADC clients (in session images)

| CLI | Package | Example |
|-----|---------|---------|
| `cadcget`, `cadcput` | cadcdata | `cadcget cadc:CFHT/806045o.fits "${TMP_SCRATCH_DIR}/"` |
| `cadc-tap` | cadctap | `cadc-tap "SELECT * FROM caom2.Observation LIMIT 5"` |
| `vcp`, `vls` | vos | `vls vos:/` |
| `canfar` | canfar | `canfar ps` |

Auth:

```bash
canfar auth login              # Science Platform
cadc-get-cert -u "$USER"       # X509 for vos/cadcdata when needed
```

In project code, pin versions in pixi/uv:

```bash
pixi add cadcdata cadctap vos canfar
```

`astroai-lab doctor` reports whether `canfar`, `cadcget`, `pixi`, and `uv` are available.

---

## Command reference

| Command | Purpose |
|---------|---------|
| `astroai-lab` | Brief status |
| `astroai-lab guide` | Printable cheat sheet |
| `astroai-lab status` | Quotas, home breakdown, team projects (access/ACL/GMS/vault), `canfar auth`/`canfar ps`, processes |
| `astroai-lab doctor [--json]` | Paths, caches, tools |
| `astroai-lab init NAME` | New pixi/uv project |
| `astroai-lab clone REPO` | `gh` clone + install |
| `astroai-lab save [NAME]` | Lockfile manifest → `~/.astroai/lab/saves/` |
| `astroai-lab resume NAME` | Restore saved env |
| `astroai-lab saves` | List saves (`--json`) |
| `astroai-lab push` | Git push + env save |
| `astroai-lab env export` | Bash `export` lines for shells |
| `astroai-lab env install-shell DEST` | Install profile/hooks (image maintainers) |
| `astroai-lab agent setup` | MCP + skills (once per user) |
| `astroai-lab agent install TOOL` | AI CLI → `$ASTROAI_LAB_BIN_DIR` |
| `astroai-lab agent models free` | Free-tier model presets |

Add **`--json`** for scripts; **`--yes`** to skip prompts.

Full flag lists: [cli.md](cli.md).

---

## AI coding agents

```bash
astroai-lab agent setup
astroai-lab agent install kilo    # or goose, cline, opencode, codex, agent
astroai-lab agent models free
astroai-lab agent update          # after image upgrade
```

Installs go to **`$ASTROAI_LAB_BIN_DIR`** (scratch when mounted, not `$HOME`).

List tools: `astroai-lab agent install --list`

---

## Examples

**Shared ML env across clones:**

```bash
astroai-lab init ml-base && cd ml-base
pixi add torch numpy
astroai-lab save ml-base
astroai-lab clone --from-env ml-base owner/project-a
```

**Non-interactive push (hooks / CI inside session):**

```bash
astroai-lab --yes push
# or: astroai-lab push --yes
```

**Scriptable diagnostics:**

```bash
astroai-lab doctor --json | jq .tools
astroai-lab status --json
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Lost code | `git push` or `astroai-lab push` before closing |
| `cadcget` auth | `cadc-get-cert -u $USER` |
| Home quota full | `astroai-lab clean home --all-safe` |
| Caches on `/arc/home` | `astroai-lab doctor` — should show scratch paths when mounted |
| Agent missing | `echo $ASTROAI_LAB_BIN_DIR`; new shell or `hash -r` |

---

## See also

- [CANFAR platform docs](https://opencadc.github.io/canfar/)
- [AstroAI session guide](https://github.com/astroai/astroai-containers/blob/main/docs/USAGE.md) — images, GPU, CVMFS, portal
