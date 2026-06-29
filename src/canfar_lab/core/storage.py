from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import humanize

from canfar_lab.core.paths import quota_used_pct
from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run


@dataclass
class QuotaLine:
    label: str
    used: str
    total: str
    pct: int


def df_line(path: Path, label: str) -> QuotaLine | None:
    if not path.is_dir():
        return None
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    pct = quota_used_pct(path) or int((usage.used / usage.total) * 100) if usage.total else 0
    return QuotaLine(
        label=label,
        used=humanize.naturalsize(usage.used, binary=True),
        total=humanize.naturalsize(usage.total, binary=True),
        pct=pct,
    )


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def home_breakdown(home: Path) -> list[tuple[str, str, str]]:
    entries = [
        (".cache", "ML/tool caches"),
        (".canfar", "CANFAR client + lab saves"),
        (".pixi", "pixi global envs"),
        (".local", "user tools and data"),
        (".config", "application config"),
    ]
    rows: list[tuple[str, str, str]] = []
    for dirname, label in entries:
        p = home / dirname
        if p.exists():
            rows.append((dirname, humanize.naturalsize(dir_size(p), binary=True), label))
    return rows


def top_cpu_processes(limit: int = 5) -> list[str]:
    try:
        from canfar_lab.utils.subprocess import run_capture

        out = run_capture(["ps", "aux", "--sort=-%cpu"])
        lines = out.splitlines()
        return lines[1 : limit + 1] if len(lines) > 1 else []
    except LabError:
        return []


def rsync_copy(source: Path, target: Path, *, dry_run: bool = False) -> None:
    if shutil.which("rsync") is None:
        raise LabError("rsync is required.", hint="Install rsync on the session image.")
    flags = ["rsync", "-avh"]
    if dry_run:
        flags.append("--dry-run")
    else:
        flags.append("--progress")
    if source.is_dir():
        flags.extend([f"{source}/", str(target)])
    else:
        flags.extend([str(source), str(target)])
    run(flags)


def stage_data(source: Path, target: Path, *, yes: bool = False, dry_run: bool = False) -> None:
    if not source.exists():
        raise LabError(f"Source not found: {source}")
    if target.exists() and not yes and not dry_run:
        raise LabError(
            f"Target exists: {target}",
            hint="canfar-lab data stage ... --yes  # overwrite",
        )
    rsync_copy(source, target, dry_run=dry_run)


def sync_data(
    source: Path,
    target: Path,
    scratch: Path | None,
    *,
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    if not source.exists():
        raise LabError(f"Source not found: {source}")
    if scratch and not str(source).startswith(str(scratch)) and not yes:
        raise LabError(
            f"Source is not under scratch ({scratch}): {source}",
            hint="canfar-lab data sync ... --yes  # continue anyway",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    rsync_copy(source, target, dry_run=dry_run)


def list_arc_projects() -> list[Path]:
    root = Path("/arc/projects")
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and os.access(p, os.R_OK))
