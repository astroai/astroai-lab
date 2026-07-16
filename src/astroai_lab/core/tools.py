"""Session tool inventory and health checks."""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from astroai_lab.core.git import git_status
from astroai_lab.core.paths import quota_used_pct, resolve_paths
from astroai_lab.errors import LabError
from astroai_lab.utils.subprocess import run_capture

# (command, version args) — empty args means presence-only.
TOOL_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("git", ("--version",)),
    ("gh", ("--version",)),
    ("pixi", ("--version",)),
    ("uv", ("--version",)),
    ("jq", ("--version",)),
    ("rg", ("--version",)),
    ("fd", ("--version",)),
    ("bat", ("--version",)),
    ("fzf", ("--version",)),
    ("peek", ()),
    ("canfar", ("--version",)),
    ("astroai-lab", ("--version",)),
    ("cadcget", ()),
    ("cadc-tap", ()),
    ("vcp", ()),
    ("rsync", ("--version",)),
    ("jupyter", ("--version",)),
    ("delta", ("--version",)),
    ("htop", ()),
    ("ncdu", ()),
    ("tldr", ()),
    ("hyperfine", ("--version",)),
)

# Subset used by doctor for backward-compatible JSON keys.
DOCTOR_TOOL_NAMES: tuple[str, ...] = (
    "git",
    "gh",
    "pixi",
    "uv",
    "jq",
    "rg",
    "canfar",
    "rsync",
    "jupyter",
)


@dataclass(frozen=True)
class ToolInfo:
    name: str
    available: bool
    path: str | None
    version: str | None


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str


def _first_version_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return None


def tool_info(name: str, version_args: tuple[str, ...] = ()) -> ToolInfo:
    path = shutil.which(name)
    if path is None:
        return ToolInfo(name=name, available=False, path=None, version=None)
    version: str | None = None
    if version_args:
        try:
            out = run_capture([name, *version_args])
            version = _first_version_line(out)
        except LabError:
            version = None
    return ToolInfo(name=name, available=True, path=path, version=version)


def inventory_tools(
    specs: tuple[tuple[str, tuple[str, ...]], ...] = TOOL_SPECS,
) -> list[ToolInfo]:
    return [tool_info(name, args) for name, args in specs]


def doctor_tools() -> dict[str, bool]:
    return {name: shutil.which(name) is not None for name in DOCTOR_TOOL_NAMES}


def paths_dict() -> dict[str, str | None]:
    paths = resolve_paths()
    return {
        "work_dir": str(paths.work_dir),
        "scratch_dir": str(paths.scratch_dir) if paths.scratch_dir else None,
        "save_dir": str(paths.save_dir),
        "config_dir": str(paths.config_dir),
        "home": str(paths.home),
        "user_bin": str(paths.user_bin),
        "npm_prefix": str(paths.npm_prefix),
        "runtime_root": str(paths.runtime_root),
        "arc_projects": str(paths.arc_projects) if paths.arc_projects else None,
        "pixi_cache_dir": str(paths.pixi_cache_dir) if paths.pixi_cache_dir else None,
        "uv_cache_dir": str(paths.uv_cache_dir) if paths.uv_cache_dir else None,
        "pip_cache_dir": str(paths.pip_cache_dir) if paths.pip_cache_dir else None,
        "cwd": str(Path.cwd()),
    }


def _writable(path: Path | None) -> bool:
    return bool(path and path.is_dir() and os.access(path, os.W_OK))


def _creatable(path: Path | None) -> bool:
    """True if path exists and is writable, or an ancestor can create it."""
    if path is None:
        return False
    current = path
    while True:
        if current.exists():
            return current.is_dir() and os.access(current, os.W_OK)
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _astroai_lab_available() -> ToolInfo:
    """Prefer PATH; fall back to importable package (uv run / editable installs)."""
    info = tool_info("astroai-lab", ("--version",))
    if info.available:
        return info
    try:
        from astroai_lab import __version__

        return ToolInfo(
            name="astroai-lab",
            available=True,
            path="(importable)",
            version=f"astroai-lab {__version__}",
        )
    except ImportError:
        return info


def run_checks(*, warn_home_pct: int = 90) -> list[CheckItem]:
    """Return session health items. Failures are items with ok=False."""
    paths = resolve_paths()
    items: list[CheckItem] = []

    items.append(
        CheckItem(
            "work_dir",
            _writable(paths.work_dir),
            f"{paths.work_dir}" + ("" if _writable(paths.work_dir) else " (not writable)"),
        )
    )
    if paths.scratch_dir is None:
        # Outside Skaha sessions scratch may be unset; warn but do not fail.
        items.append(CheckItem("scratch_dir", True, "not mounted"))
    else:
        items.append(
            CheckItem(
                "scratch_dir",
                _writable(paths.scratch_dir),
                f"{paths.scratch_dir}"
                + ("" if _writable(paths.scratch_dir) else " (not writable)"),
            )
        )
    items.append(
        CheckItem(
            "save_dir",
            _creatable(paths.save_dir),
            str(paths.save_dir),
        )
    )
    items.append(
        CheckItem(
            "user_bin",
            _creatable(paths.user_bin),
            str(paths.user_bin),
        )
    )

    home_pct = quota_used_pct(paths.home)
    if home_pct is None:
        items.append(CheckItem("home_quota", True, "unknown"))
    else:
        items.append(
            CheckItem(
                "home_quota",
                home_pct < warn_home_pct,
                f"{home_pct}% used (warn ≥{warn_home_pct}%)",
            )
        )

    # Required: git + astroai-lab. Project managers are recommended (strict requires them).
    git_info = tool_info("git", ("--version",))
    items.append(
        CheckItem("git", git_info.available, git_info.version or git_info.path or "missing")
    )
    lab_info = _astroai_lab_available()
    items.append(
        CheckItem(
            "astroai-lab",
            lab_info.available,
            lab_info.version or lab_info.path or "missing",
        )
    )

    for name in ("pixi", "uv", "gh", "rg", "jq", "canfar"):
        info = tool_info(name, ("--version",) if name in ("pixi", "uv", "gh", "canfar") else ())
        if info.available:
            items.append(CheckItem(name, True, info.version or info.path or "ok"))
        else:
            items.append(CheckItem(name, True, "missing (recommended)"))

    git = git_status()
    if git.in_repo and git.uncommitted:
        items.append(
            CheckItem(
                "git_dirty",
                True,
                "uncommitted changes — commit or astroai-lab push before closing",
            )
        )
    elif git.in_repo:
        items.append(CheckItem("git_dirty", True, "clean"))
    else:
        items.append(CheckItem("git_dirty", True, "not a git repo"))

    return items


def checks_ok(items: list[CheckItem], *, strict: bool = False) -> bool:
    if not all(i.ok for i in items):
        return False
    if strict:
        for i in items:
            if "missing (recommended)" in i.detail:
                return False
    return True


def tools_as_dicts(tools: list[ToolInfo]) -> list[dict[str, str | bool | None]]:
    return [asdict(t) for t in tools]


def checks_as_dicts(items: list[CheckItem]) -> list[dict[str, str | bool]]:
    return [asdict(i) for i in items]


__all__ = [
    "CheckItem",
    "DOCTOR_TOOL_NAMES",
    "TOOL_SPECS",
    "ToolInfo",
    "checks_as_dicts",
    "checks_ok",
    "doctor_tools",
    "inventory_tools",
    "paths_dict",
    "run_checks",
    "tool_info",
    "tools_as_dicts",
]
