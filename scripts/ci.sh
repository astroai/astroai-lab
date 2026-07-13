#!/usr/bin/env bash
# Full local CI for astroai-lab. GitHub Actions runs a minimal pytest-only gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required (https://docs.astral.sh/uv/)" >&2
    exit 1
fi

uv sync --all-extras --quiet

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format"
uv run ruff format --check .

echo "==> pytest"
uv run pytest -q

echo "ok: all local CI checks passed"
