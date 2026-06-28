# canfar-lab

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

Use **`canfar`** to authenticate and manage sessions from anywhere. Use **`canfar-lab`**
inside a running session for day-to-day work: clone repos, manage pixi/uv environments,
and inspect storage paths.

## Install

```bash
pip install canfar-lab
# or during development:
uv tool install /path/to/canfar-lab
```

## Quick start

```bash
canfar-lab doctor
canfar-lab project new mylab
canfar-lab clone owner/repo
canfar-lab clone --from-env ml-base owner/repo
canfar-lab env save mylab
canfar-lab env resume mylab
canfar-lab env list
```

Machine-readable output:

```bash
canfar-lab doctor --json
canfar-lab env list --json
```

## Configuration

Settings live under **`~/.canfar/lab/`** (alongside the main client config in
`~/.canfar/config.yaml`).

| Variable | Purpose | Session fallback |
|----------|---------|------------------|
| `CANFAR_LAB_WORK_DIR` | Ephemeral code root | `TMP_SRC_DIR`, `/srcdir` |
| `CANFAR_LAB_SCRATCH_DIR` | Ephemeral data / package caches | `TMP_SCRATCH_DIR`, `/scratch` |
| `CANFAR_LAB_SAVE_DIR` | Persistent env saves | `~/.canfar/lab/saves` |

Skaha sessions typically inject `TMP_SRC_DIR` and `TMP_SCRATCH_DIR` — `canfar-lab`
reads those automatically when `CANFAR_LAB_*` is unset.

## Portable projects

`canfar-lab clone --from-env` only bootstraps locally (cache warm + optional lock copy).
Published repos remain standard:

```bash
git clone https://github.com/you/project.git && cd project
pixi install   # or uv sync
```

## Relationship to `canfar`

| Tool | Scope |
|------|-------|
| [`canfar`](https://github.com/opencadc/canfar) | Platform client — auth, sessions, images |
| **`canfar-lab`** | Session workbench — code, deps, scratch, `/arc` |

## Development

```bash
uv sync --all-extras
uv run canfar-lab --help
uv run pytest
```

## License

GNU Affero General Public License v3.0 or later — same as the [canfar](https://github.com/opencadc/canfar) client.
