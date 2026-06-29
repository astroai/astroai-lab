from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import humanize

from canfar_lab.core.paths import quota_used_pct
from canfar_lab.core.session_common import find_arc_project_root
from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run


@dataclass
class QuotaLine:
    label: str
    path: str
    used: str
    total: str
    free: str
    pct: int
    current: bool = False


def df_line(path: Path, label: str, *, current: bool = False) -> QuotaLine | None:
    if not path.is_dir():
        return None
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    pct = quota_used_pct(path) or int((usage.used / usage.total) * 100) if usage.total else 0
    return QuotaLine(
        label=label,
        path=str(path),
        used=humanize.naturalsize(usage.used, binary=True),
        total=humanize.naturalsize(usage.total, binary=True),
        free=humanize.naturalsize(usage.free, binary=True),
        pct=pct,
        current=current,
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


@dataclass
class ArcProjectInfo:
    name: str
    path: Path
    quota: QuotaLine | None
    is_cwd: bool


def arc_project_statuses(start: Path | None = None) -> tuple[ArcProjectInfo | None, list[ArcProjectInfo]]:
    """Team projects under /arc/projects the user can read, with quota lines."""
    cwd_root = find_arc_project_root(start)
    active: ArcProjectInfo | None = None
    rows: list[ArcProjectInfo] = []
    for proj in list_arc_projects():
        info = ArcProjectInfo(
            name=proj.name,
            path=proj,
            quota=df_line(proj, proj.name, current=(cwd_root == proj)),
            is_cwd=cwd_root == proj,
        )
        rows.append(info)
        if info.is_cwd:
            active = info
    rows.sort(key=lambda row: (not row.is_cwd, row.name.lower()))
    return active, rows


def collect_status_quotas(
    *,
    home: Path,
    scratch: Path | None,
) -> list[QuotaLine]:
    quotas: list[QuotaLine] = []
    if q := df_line(home, "home"):
        quotas.append(q)
    _, projects = arc_project_statuses()
    for proj in projects:
        if proj.quota is not None:
            quotas.append(proj.quota)
        elif proj.is_cwd:
            quotas.append(
                QuotaLine(
                    label=proj.name,
                    path=str(proj.path),
                    used="?",
                    total="?",
                    free="?",
                    pct=0,
                    current=True,
                )
            )
    if scratch is not None:
        if q := df_line(scratch, "scratch"):
            quotas.append(q)
    return quotas
