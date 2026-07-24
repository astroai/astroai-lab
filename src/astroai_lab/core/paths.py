from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from astroai_lab.core.disk_usage import disk_usage, quota_used_pct
from astroai_lab.core.session_common import find_arc_project_root, scratch_cache_root
from astroai_lab.shell.session_env import resolve_session_env


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


def _first_writable(path: Path) -> Path | None:
    if path.is_dir() and os.access(path, os.W_OK):
        return path
    return None


def resolve_paths() -> SessionPaths:
    env = resolve_session_env(ensure=False)

    return SessionPaths(
        work_dir=env.tmp_src_dir,
        scratch_dir=env.tmp_scratch_dir,
        save_dir=env.astroai_lab_save_dir,
        config_dir=env.astroai_lab_config_dir,
        home=Path.home(),
        user_bin=env.astroai_lab_bin_dir,
        npm_prefix=env.astroai_lab_npm_prefix,
        runtime_root=env.astroai_lab_runtime_root,
        arc_projects=Path("/arc/projects") if Path("/arc/projects").is_dir() else None,
        pixi_cache_dir=_first_writable(env.pixi_cache_dir),
        uv_cache_dir=_first_writable(env.uv_cache_dir),
        pip_cache_dir=_first_writable(env.pip_cache_dir),
    )


def workspace_root(work_dir: Path) -> Path:
    return work_dir / ".astroai-lab" / "workspaces"


def user_bin_dir() -> Path:
    return resolve_session_env(ensure=False).astroai_lab_bin_dir


def npm_prefix_dir() -> Path:
    return resolve_session_env(ensure=False).astroai_lab_npm_prefix


def runtime_root(work_dir: Path, scratch: Path | None) -> Path:
    return resolve_session_env(ensure=False).astroai_lab_runtime_root


__all__ = [
    "SessionPaths",
    "disk_usage",
    "find_arc_project_root",
    "npm_prefix_dir",
    "quota_used_pct",
    "resolve_paths",
    "runtime_root",
    "scratch_cache_root",
    "user_bin_dir",
    "workspace_root",
]
