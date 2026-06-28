from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from canfar_lab import config_dir
from canfar_lab.config import get_settings


@dataclass(frozen=True)
class SessionPaths:
    """Resolved session storage and cache paths."""

    work_dir: Path
    scratch_dir: Path | None
    save_dir: Path
    config_dir: Path
    home: Path
    arc_projects: Path | None
    pixi_cache_dir: Path | None
    uv_cache_dir: Path | None
    pip_cache_dir: Path | None


def _first_writable(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir() and os.access(path, os.W_OK):
            return path
    return None


def scratch_cache_root(work: Path, scratch: Path | None) -> Path:
    user = os.environ.get("USER") or "user"
    if scratch is not None:
        return scratch / f".cache-{user}"
    return work / f".cache-{user}"


def resolve_paths() -> SessionPaths:
    settings = get_settings()
    work = settings.resolve_work_dir()
    scratch = settings.resolve_scratch_dir()
    cache_root = scratch_cache_root(work, scratch)

    return SessionPaths(
        work_dir=work,
        scratch_dir=scratch,
        save_dir=settings.resolve_save_dir(),
        config_dir=config_dir(),
        home=Path.home(),
        arc_projects=Path("/arc/projects") if Path("/arc/projects").is_dir() else None,
        pixi_cache_dir=_first_writable(
            Path(os.environ["PIXI_CACHE_DIR"]) if os.environ.get("PIXI_CACHE_DIR") else cache_root / "pixi",
            cache_root / "pixi",
        ),
        uv_cache_dir=_first_writable(
            Path(os.environ["UV_CACHE_DIR"]) if os.environ.get("UV_CACHE_DIR") else cache_root / "uv",
            cache_root / "uv",
        ),
        pip_cache_dir=_first_writable(
            Path(os.environ["PIP_CACHE_DIR"]) if os.environ.get("PIP_CACHE_DIR") else cache_root / "pip",
            cache_root / "pip",
        ),
    )


def quota_used_pct(path: Path) -> int | None:
    if not path.is_dir():
        return None
    try:
        stat = os.statvfs(path)
    except OSError:
        return None
    total = stat.f_blocks * stat.f_frsize
    if total <= 0:
        return None
    used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
    return int((used / total) * 100)
