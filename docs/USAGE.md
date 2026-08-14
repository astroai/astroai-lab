# astroai-lab usage

**astroai-lab** is the in-session workbench for AstroAI sessions on the
[CANFAR Science Platform](https://www.opencadc.org/canfar/). It is intentionally
small: **environment save/resume** plus **AI agent management**, with a few
supporting commands.

It works alongside:

| Tool | Role |
|------|------|
| [`canfar`](https://github.com/opencadc/canfar) | Platform auth, session lifecycle, `canfar data` archive I/O |
| CADC clients (`cadcget`, `cadc-tap`, `vcp`, …) | Archive and VOSpace I/O in session images |
| [Session images](https://github.com/astroai/astroai-containers) | `webterm`, `notebook`, `vscode`, `marimo`, Ray |

| Doc | Scope |
|-----|--------|
| **USAGE.md** (this file) | Narrative: where to work, storage, workflows |
| [help.md](help.md) | Short session loop |
| [cli.md](cli.md) | Full CLI reference |
| [config.md](config.md) | Optional `~/.astroai/lab/config.yaml` |

In a session: `astroai-lab help` · `less /opt/astroai/USAGE.md` (image user guide).

Platform docs: [opencadc.github.io/canfar](https://opencadc.github.io/canfar/)

---

## Where you work

```mermaid
flowchart TB
  subgraph outside [Laptop or browser]
    SP[Science Portal]
    CF["canfar login / create / ps"]
  end
  subgraph session [AstroAI session]
    AL[astroai-lab]
    PM[pixi / uv]
    NB[Jupyter / marimo]
    CADC[vcp / cadcget / …]
  end
  SP --> session
  CF --> session
  AL --> PM
  AL --> NB
  AL --> CADC
```

| Where | What you do | Tools |
|-------|-------------|--------|
| **Laptop / browser** | Log in, start and stop sessions | Science Portal, or `canfar login` / `canfar create` / `canfar ps` |
| **Inside a session** | Code, notebooks, training, agents | `astroai-lab`, Jupyter, pixi/uv, CADC clients |

`astroai-lab` commands run **inside** the session (terminal, notebook cell, or VS Code).

### Student path (notebook-first)

1. Open the [Science Portal](https://www.canfar.net/science-portal) → launch **notebook** or **marimo** (pick a GPU node only if you need a GPU).
2. **Jupyter:** open `/opt/astroai/notebooks/starter.ipynb` and select the AstroAI kernel (`astroai-lab kernel ensure` if needed).
3. **Marimo:** the session opens `$WORK/notebooks/starter.py` (seeded once).
4. Run `astroai-lab status` to check paths and quotas.
5. Keep long-lived results with `canfar data` or `vcp` to VOSpace.
6. Later: `astroai-lab init` / `clone` plus pixi or uv for project environments.

VOSpace: use **`vls` / `vcp`** from the image (or the interim Vault widget in the
marimo starter). There is no separate `astroai-lab` VOSpace wrapper.

---

## Install

Session images ship `astroai-lab` on PATH under `/opt/astroai/venv/cadc`.

Elsewhere (GitHub; not required for portal users):

```bash
uv tool install git+https://github.com/astroai/astroai-lab.git
pip install "git+https://github.com/astroai/astroai-lab.git"
```

Development checkout:

```bash
uv sync --all-extras
uv run astroai-lab --help
./scripts/ci.sh
```

---

## First project

```bash
astroai-lab init mylab
cd "$WORK/mylab"
pixi add numpy
pixi run python -c "import numpy; print(numpy.__version__)"
astroai-lab save mylab
```

Clone an existing GitHub repo (needs `gh auth login` once):

```bash
astroai-lab clone owner/repo
astroai-lab clone --from-env mylab owner/repo   # optional: warm from a named save
```

The env snapshot (`save`) writes lockfiles + manifest to `~/.astroai/lab/saves/`
on `/arc/home`, so a future session can `resume` it:

```mermaid
flowchart TD
  I[init or clone] --> W[Edit and run under $WORK]
  W --> S[save]
  S --> W
  S --> R[resume in the next session]
```

---

## Storage

| Tier | Env / path | Lifetime | Use for |
|------|------------|----------|---------|
| Work | `WORK` (`/srcdir`) | Session | Source trees, pixi/uv projects |
| Scratch | `SCRATCH` (`/scratch`) | Session | Datasets, build caches, temp |
| Home | `/arc/home/<you>` | Persistent | Config, `~/.astroai/lab/saves/`, certs |
| Projects | `/arc/projects/<group>` | Persistent | Shared data and team env-saves |

Inspect quotas and home usage:

```bash
astroai-lab status
astroai-lab status --json
```

Move data with the platform client:

```bash
canfar data …        # archive I/O
vcp ./local.fits vos:…
```

---

## Working with `canfar` and CADC

From a laptop or any AstroAI session:

```bash
canfar login
canfar create --name demo webterm
canfar ps
canfar open <session-id>
canfar delete <session-id>
```

CADC / VOSpace examples (image PATH):

```bash
cadcget …
vls vos:…
vcp ./local.fits vos:…
```

`astroai-lab status` includes `canfar auth show` and `canfar ps` when the CLI is available.

---

## Command map

| Goal | Command |
|------|---------|
| Status banner | `astroai-lab` |
| New project | `astroai-lab init NAME` |
| Clone + install | `astroai-lab clone REPO` |
| Snapshot env | `astroai-lab save [NAME]` |
| Restore env | `astroai-lab resume NAME` |
| List saves | `astroai-lab saves` |
| Quotas / sessions | `astroai-lab status` |
| Jupyter kernel | `astroai-lab kernel ensure` |
| Agents | `astroai-lab agent setup\|install\|…` |

Full flags: [cli.md](cli.md).

---

## Shell completion

Enable tab-completion once per shell (bash, zsh, or fish):

```bash
astroai-lab --install-completion bash   # or zsh, fish
```

Completions cover **command paths** and **option values** where they are
enumerable, so you rarely need to guess or re-read `help`:

- **Command paths** for `help -c` — type a prefix and press Tab:

  ```bash
  astroai-lab help -c "agent l"<TAB>    # → agent list
  astroai-lab help -c env<TAB>          # → env export
  ```


- **Registered kernel names** for `kernel unregister` / `kernel ensure --name`:

  ```bash
  astroai-lab kernel unregister <TAB>   # → kernels you have registered
  ```

- **Installable CLIs** for `agent install`, **bundles + registered agent ids**
  for `agent setup`, **registered agent ids** for `agent config`/`agent update`,
  and **plugin ids** for `agent plugins install`:

  ```bash
  astroai-lab agent install <TAB>       # → kilo, goose, opencode, …
  astroai-lab agent setup <TAB>         # → cursor, claude, hermes, …
  astroai-lab agent config <TAB>        # → kilo, goose, hermes, openclaw, …
  astroai-lab agent plugins install <TAB>  # → ponytail, polars, …
  ```

- **`--kind` filters** for `agent plugins list`:

  ```bash
  astroai-lab agent plugins list --kind <TAB>  # → skill, mcp, …
  ```

---

## AI coding agents

Configs/skills persist under `/arc` home; CLI binaries install to `$SCRATCH` (`$ASTROAI_LAB_BIN_DIR`).

**`agent list` is the installable set.** Each agent is one YAML file
(`data/agent/agents/<id>.yaml`): how it installs, where config lives, how it
verifies. `agent list` / `install` / `remove` share that set. Configs stay on
`$HOME`; CLIs go to scratch.

```bash
astroai-lab agent list             # installable agents (Bin / Cfg / Where / Ver)
astroai-lab agent install kilo     # CLI → $SCRATCH (also: cursor, claude, goose, …)
astroai-lab agent remove kilo      # managed scratch CLI; --clean-home for $HOME copies
astroai-lab agent remove kilo --purge  # also drop config dirs (~/.config/kilo, …)
astroai-lab agent wipe             # factory reset (confirm or --yes; --dry-run to preview)
astroai-lab agent setup hermes     # settings scaffold + skills + plugins
astroai-lab agent setup --all      # same for every managed install
astroai-lab agent setup --project  # per-repo AGENTS.md + .cursor scaffold
astroai-lab agent config hermes    # show/edit $HOME settings (key=value / --unset)
astroai-lab agent plugins list     # Kind / On / Def / Agents; --description for summaries
astroai-lab agent plugins install ponytail
astroai-lab agent update           # after upgrading lab in-session
astroai-lab agent update hermes    # refresh ONE agent
astroai-lab agent verify           # config syntax + presence checks
astroai-lab agent verify --fix     # auto-repair, then re-check
astroai-lab agent verify --clean    # clear stale locks / markers
```

Upgrade lab in a running session (no image rebuild): see “Writable CADC venv”
in astroai-containers CONTRIBUTING, or:

```bash
uv pip install --python /opt/astroai/venv/cadc \
  "git+https://github.com/astroai/astroai-lab.git@main"
# then open a new shell / `hash -r` so PATH picks up the new entrypoint
```

---

## Troubleshooting

| Symptom | What to run |
|---------|-------------|
| Paths look wrong / caches under `$HOME` | `astroai-lab env export` in a login shell (`bash -l`) |
| Env save failed | `astroai-lab status` (quota) |
| Kernel missing in Jupyter | `astroai-lab kernel ensure` |
| `canfar` unknown | Confirm you are on an AstroAI image |
| All command help | `astroai-lab help` |

---

## See also

- [astroai-containers USAGE](https://github.com/astroai/astroai-containers/blob/main/docs/USAGE.md) — images, portal session types
- [astroai-workload](https://github.com/astroai/astroai-workload) — submit Ray Jobs (`astroai-workload run`) on ray-manager
- [CANFAR client docs](https://opencadc.github.io/canfar/)
