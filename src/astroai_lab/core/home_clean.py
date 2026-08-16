"""Free space on home: package caches, optional saved environments and preferences."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from astroai_lab.core.disk_usage import naturalsize
from astroai_lab.core.project import save_rows
from astroai_lab.core.storage import dir_bytes

# Regenerable tool caches that leak onto /arc/home even when profile.sh
# points pip/uv/pixi at $SCRATCH.
CACHE_REL = (
    ".cache/pip",
    ".cache/uv",
    ".cache/huggingface",
    ".cache/torch",
    ".cache/pre-commit",
    ".cache/matplotlib",
    ".cache/npm",
    ".cache/yarn",
    ".cache/pixi",
    ".cache/conda",
    ".cache/pypoetry",
    ".cache/astroai-lab",
    ".local/share/uv",
    ".local/share/pip",
    ".local/share/Trash",
    ".npm/_cacache",
    ".pixi/cache",
)


def _row(path: Path, kind: str) -> dict[str, Any]:
    n = dir_bytes(path)
    size = 0 if n is None else n
    return {
        "kind": kind,
        "path": str(path),
        "bytes": size,
        "size": "—" if n is None else naturalsize(size),
    }


def plan_clean(home: Path, save_dir: Path) -> dict[str, Any]:
    """What `astroai-lab clean` can remove. Does not delete anything."""
    caches = [_row(home / rel, "cache") for rel in CACHE_REL if (home / rel).exists()]
    saves = []
    for row in save_rows(save_dir):
        path = Path(row["path"])
        item = _row(path, "save")
        item["name"] = row["name"]
        item["saved_at"] = row["saved_at"]
        item["env_kind"] = row["kind"]
        saves.append(item)
    cfg = home / ".astroai" / "lab" / "config.yaml"
    config = _row(cfg, "config") if cfg.exists() else None
    return {
        "caches": caches,
        "saves": saves,
        "config": config,
        "cache_bytes": sum(r["bytes"] for r in caches),
        "save_bytes": sum(r["bytes"] for r in saves),
    }


def _rm(path: Path) -> dict[str, str]:
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return {"path": str(path), "status": "removed"}
    except OSError as exc:
        return {"path": str(path), "status": "error", "detail": str(exc)}


def apply_clean(
    plan: dict[str, Any],
    *,
    caches: bool,
    saves: bool,
    config: bool,
    dry_run: bool,
) -> list[dict[str, str]]:
    """Delete selected plan rows. ``dry_run`` reports ``would_remove`` only."""
    actions: list[dict[str, str]] = []
    selected: list[dict[str, Any]] = []
    if caches:
        selected.extend(plan["caches"])
    if saves:
        selected.extend(plan["saves"])
    if config and plan["config"] is not None:
        selected.append(plan["config"])
    for row in selected:
        path = Path(row["path"])
        if dry_run:
            actions.append({"path": str(path), "status": "would_remove"})
            continue
        actions.append(_rm(path))
    return actions
