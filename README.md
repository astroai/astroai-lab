# canfar-lab

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

Use **`canfar`** to authenticate and manage sessions. Use **`canfar-lab`** inside a running session for the daily workflow: init/clone, save/resume environments, push before closing.

## AI coding agents

```bash
canfar-lab agent setup              # once per user — MCP + skills (persists on /arc)
canfar-lab agent install kilo       # or goose, cline, opencode, codex, agent
canfar-lab agent models free        # OpenRouter + Kilo free-tier model presets
gh auth login                       # GitHub for gh + GitHub MCP
```

Refresh after image upgrade: `canfar-lab agent update`

See [docs/cli.md](docs/cli.md) for `canfar-lab agent models --preset long` and per-agent setup.

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
canfar-lab paths            # work / scratch / cache paths
canfar-lab tools            # tools on PATH
canfar-lab check            # quick health check
```

Machine-readable output: add **`--json`** to list/status/paths/tools/check/doctor commands.

## Configuration

Paths auto-detect from Skaha session variables (`TMP_SRC_DIR`, `TMP_SCRATCH_DIR`).
Optional preferences: **`~/.canfar/lab/config.yaml`**.

| Doc | Scope |
|-----|--------|
| [docs/USAGE.md](docs/USAGE.md) | **canfar-lab** — commands, storage, CADC/canfar integration, agents |
| [docs/guide.md](docs/guide.md) | Short session loop |
| [docs/cli.md](docs/cli.md) | Full CLI reference |

**AstroAI session images** (webterm, notebook, …): [containers USAGE](https://github.com/astroai/containers/blob/main/docs/USAGE.md).

## Relationship to `canfar`

| Tool | Scope |
|------|-------|
| [`canfar`](https://github.com/opencadc/canfar) | Platform client — auth, sessions, images |
| **`canfar-lab`** | Session workbench — code, deps, scratch, `/arc` |

## Development

Run the full check suite locally before pushing:

```bash
./scripts/ci.sh
```

That runs ruff (lint + format), then pytest with coverage. GitHub Actions only runs pytest as a lightweight gate.

Manual steps:

```bash
uv sync --all-extras
uv run canfar-lab guide
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Shell completion: `canfar-lab --install-completion bash`

## License

The canfar-lab project code is licensed under the [MIT License](LICENSE).
The external [canfar client](https://github.com/opencadc/canfar) retains its
own upstream license and notices.
