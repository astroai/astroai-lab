#!/usr/bin/env bash
# Full local CI for astroai-lab — mirrors .github/workflows/ci.yml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required (https://docs.astral.sh/uv/)" >&2
    exit 1
fi

uv sync --all-extras --quiet
uv lock --check

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format"
uv run ruff format --check .

echo "==> ty check"
# CONDA_PREFIX can point ty at a conda site-packages on some dev machines.
env -u CONDA_PREFIX uv run ty check src/astroai_lab

echo "==> CLI audit"
bash scripts/audit-cli-help.sh

echo "==> pytest"
uv run pytest -q

echo "ok: all local CI checks passed"
