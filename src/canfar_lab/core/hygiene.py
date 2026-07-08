from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import humanize

from canfar_lab.utils.subprocess import run


@dataclass
class CleanTarget:
    path: Path
    label: str
    bytes: int


HOME_PROTECTED = (
    ".ssh",
    ".config",
    ".canfar/lab/saves",
    ".local/bin",
    ".local/share/uv/python",
    ".local/share/uv/tools",
)

HOME_STALE_PKG = (
    ".cache/pip",
    ".cache/uv",
    ".cache/npm",
    ".cache/pixi",
    ".cache/conda",
)

HOME_ML = (
    ".cache/torch",
    ".cache/matplotlib",
    ".cache/huggingface",
    ".cache/numba",
    ".cache/jupyter",
    ".cache/ipython",
)

HOME_XDG_JUNK = (
    ".cache/pre-commit",
    ".cache/mypy",
    ".cache/pytest",
    ".cache/ruff",
)


def _under_home(path: Path, home: Path) -> bool:
    try:
        path.resolve().relative_to(home.resolve())
        return True
    except ValueError:
        return False


def _is_protected(path: Path, home: Path) -> bool:
    rel = str(path.resolve().relative_to(home.resolve())) if _under_home(path, home) else ""
    for prot in HOME_PROTECTED:
        if rel == prot or rel.startswith(prot + "/"):
            return True
    return False


def _path_bytes(path: Path) -> int:
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return path.stat().st_size


def collect_home_targets(
    home: Path,
    *,
    stale_pkg: bool,
    ml: bool,
    hf: bool,
    xdg_junk: bool,
) -> list[CleanTarget]:
    groups: list[tuple[str, ...]] = []
    if stale_pkg:
        groups.append(HOME_STALE_PKG)
    if ml and not hf:
        groups.extend(
            [
                (".cache/torch",),
                (".cache/matplotlib",),
                (".cache/numba",),
                (".cache/jupyter",),
                (".cache/ipython",),
            ]
        )
    if hf:
        groups.append((".cache/huggingface",))
    if xdg_junk:
        groups.append(HOME_XDG_JUNK)

    targets: list[CleanTarget] = []
    seen: set[Path] = set()
    for group in groups:
        for rel in group:
            path = home / rel
            if not path.exists() or path in seen or _is_protected(path, home):
                continue
            seen.add(path)
            size = _path_bytes(path)
            targets.append(CleanTarget(path=path, label=rel, bytes=size))
    return targets


def apply_clean(targets: list[CleanTarget], *, dry_run: bool) -> int:
    total = 0
    for t in targets:
        total += t.bytes
        if dry_run:
            continue
        if t.path.is_dir():
            shutil.rmtree(t.path)
        else:
            t.path.unlink(missing_ok=True)
    return total


def collect_cache_targets(
    *,
    pip: bool,
    uv_cache: bool,
    npm: bool,
    pixi: bool,
    conda: bool,
    hf: bool,
) -> list[CleanTarget]:
    from canfar_lab.shell.session_env import resolve_session_env

    env = resolve_session_env(ensure=False)

    env_map = {
        "pip": (env.pip_cache_dir, "PIP_CACHE_DIR", pip),
        "uv": (env.uv_cache_dir, "UV_CACHE_DIR", uv_cache),
        "npm": (env.npm_config_cache, "NPM_CONFIG_CACHE", npm),
        "pixi": (env.pixi_cache_dir, "PIXI_CACHE_DIR", pixi),
        "conda": (env.mamba_pkgs_dirs, "MAMBA_PKGS_DIRS", conda),
        "hf": (env.hf_home, "HF_HOME", hf),
    }
    targets: list[CleanTarget] = []
    for label, (path, var, enabled) in env_map.items():
        if not enabled:
            continue
        if not path or not path.exists():
            continue
        size = _path_bytes(path)
        targets.append(CleanTarget(path=path, label=f"{label} ({var})", bytes=size))
    return targets


def prune_uv_cache(*, dry_run: bool) -> None:
    if shutil.which("uv") is None:
        return
    if dry_run:
        return
    run(["uv", "cache", "prune"])


def format_bytes(n: int) -> str:
    return humanize.naturalsize(n, binary=True)
