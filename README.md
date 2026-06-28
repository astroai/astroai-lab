# canfar-lab

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

Use **`canfar`** to authenticate and manage sessions. Use **`canfar-lab`** inside a running session for the daily workflow: init/clone, save/resume environments, push before closing.

## Session loop

```bash
canfar-lab resume mylab     # or init / clone
cd $WORK/mylab && pixi run python analysis.py
canfar-lab save             # anytime
canfar-lab push             # before closing session
```

Run **`canfar-lab guide`** for the full cheat sheet.

## Install

```bash
pip install canfar-lab
# or during development:
uv tool install /path/to/canfar-lab
```

## Quick start

```bash
canfar-lab                  # brief status
canfar-lab init mylab
canfar-lab clone owner/repo
canfar-lab save mylab
canfar-lab resume mylab
canfar-lab push
```

Machine-readable output: add **`--json`** to list/status/doctor commands.

## Configuration

Paths auto-detect from Skaha session variables (`TMP_SRC_DIR`, `TMP_SCRATCH_DIR`).
Optional preferences: **`~/.canfar/lab/config.yaml`**.

See [docs/guide.md](docs/guide.md), [docs/cli.md](docs/cli.md), and [docs/config.md](docs/config.md).

## Relationship to `canfar`

| Tool | Scope |
|------|-------|
| [`canfar`](https://github.com/opencadc/canfar) | Platform client — auth, sessions, images |
| **`canfar-lab`** | Session workbench — code, deps, scratch, `/arc` |

## Development

```bash
uv sync --all-extras
uv run canfar-lab guide
uv run pytest -q
```

Shell completion: `canfar-lab --install-completion bash`

## License

GNU Affero General Public License v3.0 or later — same as the [canfar](https://github.com/opencadc/canfar) client.
