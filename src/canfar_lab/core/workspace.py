from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from canfar_lab.core.paths import workspace_root
from canfar_lab.core.project import require_project
from canfar_lab.errors import LabError


def _bundle_dir(work_dir: Path, name: str) -> Path:
    return workspace_root(work_dir) / name


def save_workspace(
    project_root: Path,
    work_dir: Path,
    name: str,
    *,
    with_cache: bool = False,
    dest: Path | None = None,
) -> Path:
    require_project(project_root)
    bundle = dest or _bundle_dir(work_dir, name)
    bundle.mkdir(parents=True, exist_ok=True)

    meta = {
        "name": name,
        "saved_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "saved_from": str(project_root.resolve()),
        "with_cache": with_cache,
    }
    (bundle / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")

    archive = bundle / "project.tar.zst"
    proc = subprocess.run(
        ["tar", "-C", str(project_root.parent), "-cf", "-", project_root.name],
        capture_output=True,
        check=True,
    )
    with archive.open("wb") as out:
        zstd = subprocess.Popen(["zstd", "-T0", "-"], stdin=subprocess.PIPE, stdout=out)
        assert zstd.stdin is not None
        zstd.stdin.write(proc.stdout)
        zstd.stdin.close()
        zstd.wait()

    if with_cache:
        import os

        for var in ("UV_CACHE_DIR", "PIP_CACHE_DIR", "PIXI_CACHE_DIR", "MAMBA_PKGS_DIRS"):
            raw = os.environ.get(var, "").strip()
            if raw and Path(raw).is_dir():
                label = var.lower().replace("_dir", "").replace("_", "-")
                cache_archive = bundle / f"cache-{label}.tar.zst"
                _tar_zst(Path(raw), cache_archive, arcname=Path(raw).name)

    return bundle


def restore_workspace(
    work_dir: Path,
    name: str,
    *,
    from_path: Path | None = None,
    target: Path | None = None,
) -> Path:
    bundle = from_path or _bundle_dir(work_dir, name)
    manifest = bundle / "manifest.json"
    if not manifest.is_file():
        raise LabError(
            f"Workspace bundle not found: {bundle}",
            hint="canfar-lab workspace save mylab",
        )

    dest = target or work_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)

    archive = bundle / "project.tar.zst"
    if not archive.is_file():
        raise LabError(f"Missing project archive in {bundle}")

    zstd = subprocess.Popen(["zstd", "-d", "-c", str(archive)], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-xf", "-", "-C", str(dest.parent)], stdin=zstd.stdout, check=True)
    zstd.wait()
    return dest


def _tar_zst(source: Path, dest: Path, *, arcname: str) -> None:
    proc = subprocess.run(
        ["tar", "-C", str(source.parent), "-cf", "-", arcname],
        capture_output=True,
        check=True,
    )
    with dest.open("wb") as out:
        zstd = subprocess.Popen(["zstd", "-T0", "-"], stdin=subprocess.PIPE, stdout=out)
        assert zstd.stdin is not None
        zstd.stdin.write(proc.stdout)
        zstd.stdin.close()
        zstd.wait()
