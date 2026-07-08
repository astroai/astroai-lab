from __future__ import annotations

import re
import subprocess
from pathlib import Path

from canfar_lab.core.storage import df_line
from canfar_lab.errors import LabError


def init_team_project(name: str, *, members: list[str] | None = None) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise LabError(
            f"Invalid project name '{name}'",
            hint="Use letters, digits, _, - only",
        )
    root = Path("/arc/projects")
    if not root.is_dir():
        raise LabError(
            "/arc/projects is not mounted.",
            hint="Team workspaces require CANFAR /arc/projects storage.",
        )
    proj = root / name
    for sub in ("data", "results", "env-saves"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    if members:
        for member in members:
            member = member.strip()
            if not member:
                continue
            subprocess.run(
                ["setfacl", "-R", "-m", f"u:{member}:rwx", str(proj)],
                check=False,
            )
            subprocess.run(
                ["setfacl", "-R", "-m", f"d:u:{member}:rwx", str(proj)],
                check=False,
            )
    return proj


def project_layout(proj: Path) -> list[str]:
    rows: list[str] = []
    for d in [proj, proj / "data", proj / "results", proj / "env-saves"]:
        if d.is_dir():
            rows.append(f"{d.name}/")
    return rows


def project_quota_line(proj: Path, label: str) -> str | None:
    q = df_line(proj, label)
    if q is None:
        return None
    return f"{q.used} / {q.total} ({q.pct}%) — {q.free} free"
