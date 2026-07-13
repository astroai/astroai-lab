> **Renamed from `canfar-lab`.** CLI is `astroai-lab`; config lives at `~/.astroai/lab` (one-shot migrate from `~/.canfar/lab`). There is no `canfar-lab` alias.

# astroai-lab

In-session workbench for the [CANFAR Science Platform](https://www.opencadc.org/canfar/).

Use **`canfar`** to authenticate and manage sessions. Use **`astroai-lab`** inside a running session for the daily workflow: init/clone, save/resume environments, push before closing.

## AI coding agents

```bash
astroai-lab agent setup              # once per user — MCP + skills (persists on /arc)
astroai-lab agent install kilo       # or goose, cline, opencode, codex, agent
astroai-lab agent models free        # OpenRouter + Kilo free-tier model presets
gh auth login                       # GitHub for gh + GitHub MCP
```

Refresh after image upgrade: `astroai-lab agent update`

See [docs/cli.md](docs/cli.md) for `astroai-lab agent models free --preset long` and per-agent setup.

## Session loop

```bash
astroai-lab resume mylab     # or init / clone
cd $WORK/mylab && pixi run python analysis.py
astroai-lab save             # anytime
astroai-lab push             # before closing session
```

Run **`astroai-lab guide`** for the full cheat sheet.

## Install

```bash
pip install astroai-lab
# or during development:
uv tool install /path/to/astroai-lab
```

## Quick start

```bash
astroai-lab                  # brief status
astroai-lab init mylab
astroai-lab clone owner/repo
astroai-lab save mylab
astroai-lab resume mylab
astroai-lab push
astroai-lab paths            # work / scratch / cache paths
astroai-lab tools            # tools on PATH
astroai-lab check            # quick health check
```

Machine-readable output: add **`--json`** to list/status/paths/tools/check/doctor commands.

## Configuration

Paths auto-detect from Skaha session variables (`TMP_SRC_DIR`, `TMP_SCRATCH_DIR`).
Optional preferences: **`~/.astroai/lab/config.yaml`**.

| Doc | Scope |
|-----|--------|
| [docs/USAGE.md](docs/USAGE.md) | **astroai-lab** — commands, storage, CADC/canfar integration, agents |
| [docs/guide.md](docs/guide.md) | Short session loop |
| [docs/cli.md](docs/cli.md) | Full CLI reference |

**AstroAI session images** (webterm, notebook, …): [containers USAGE](https://github.com/astroai/astroai-containers/blob/main/docs/USAGE.md).

## Relationship to `canfar`

| Tool | Scope |
|------|-------|
| [`canfar`](https://github.com/opencadc/canfar) | Platform client — auth, sessions, images |
| **`astroai-lab`** | Session workbench — code, deps, scratch, `/arc` |

## Development

Run the full check suite locally before pushing:

```bash
./scripts/ci.sh
```

That runs ruff (lint + format), then pytest with coverage. GitHub Actions only runs pytest as a lightweight gate.

Manual steps:

```bash
uv sync --all-extras
uv run astroai-lab guide
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Shell completion: `astroai-lab --install-completion bash`

## License

The astroai-lab project code is licensed under the [MIT License](LICENSE).
The external [canfar client](https://github.com/opencadc/canfar) retains its
own upstream license and notices.
