from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from canfar_lab.core.session_common import find_arc_project_root, scratch_cache_root
from canfar_lab.shell.session_env import resolve_session_env


@dataclass(frozen=True)
class SessionPaths:
    work_dir: Path
    scratch_dir: Path | None
    save_dir: Path
    config_dir: Path
    home: Path
    user_bin: Path
    npm_prefix: Path
    runtime_root: Path
    arc_projects: Path | None
    pixi_cache_dir: Path | None
    uv_cache_dir: Path | None
    pip_cache_dir: Path | None


def _first_writable(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir() and os.access(path, os.W_OK):
            return path
    return None


def _env_cache_path(var: str, default: Path) -> Path | None:
    raw = os.environ.get(var)
    return Path(raw) if raw else default


def resolve_paths() -> SessionPaths:
    env = resolve_session_env(ensure=False)
    work = env.tmp_src_dir
    scratch = env.tmp_scratch_dir
    cache_root = scratch_cache_root(work, scratch)

    return SessionPaths(
        work_dir=work,
        scratch_dir=scratch,
        save_dir=env.canfar_lab_save_dir,
        config_dir=env.canfar_lab_config_dir,
        home=Path.home(),
        user_bin=env.canfar_lab_bin_dir,
        npm_prefix=env.canfar_lab_npm_prefix,
        runtime_root=env.canfar_lab_runtime_root,
        arc_projects=Path("/arc/projects") if Path("/arc/projects").is_dir() else None,
        pixi_cache_dir=_first_writable(
            _env_cache_path("PIXI_CACHE_DIR", cache_root / "pixi") or cache_root / "pixi",
            cache_root / "pixi",
        ),
        uv_cache_dir=_first_writable(
            _env_cache_path("UV_CACHE_DIR", cache_root / "uv") or cache_root / "uv",
            cache_root / "uv",
        ),
        pip_cache_dir=_first_writable(
            _env_cache_path("PIP_CACHE_DIR", cache_root / "pip") or cache_root / "pip",
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


def workspace_root(work_dir: Path) -> Path:
    return work_dir / ".canfar-lab" / "workspaces"


def user_bin_dir() -> Path:
    return resolve_session_env(ensure=False).canfar_lab_bin_dir


def npm_prefix_dir() -> Path:
    return resolve_session_env(ensure=False).canfar_lab_npm_prefix


def runtime_root(work_dir: Path, scratch: Path | None) -> Path:
    return resolve_session_env(ensure=False).canfar_lab_runtime_root


__all__ = [
    "SessionPaths",
    "find_arc_project_root",
    "npm_prefix_dir",
    "quota_used_pct",
    "resolve_paths",
    "runtime_root",
    "scratch_cache_root",
    "user_bin_dir",
    "workspace_root",
]
