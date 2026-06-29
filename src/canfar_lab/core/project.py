from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import humanize

from canfar_lab.errors import LabError
from canfar_lab.models.manifest import EnvManifest, ProjectKind
from canfar_lab.utils.subprocess import run


def detect_project(directory: Path) -> ProjectKind | None:
    if (directory / "pixi.toml").is_file():
        return ProjectKind.PIXI
    if (directory / "pyproject.toml").is_file():
        return ProjectKind.UV
    return None


def require_project(directory: Path) -> ProjectKind:
    kind = detect_project(directory)
    if kind is None:
        raise LabError(
            "No pixi or uv project here (need pixi.toml or pyproject.toml).",
            hint="canfar-lab init mylab",
        )
    return kind


def install_project(directory: Path, *, bootstrap_lock: bool = False, quiet: bool = False) -> None:
    kind = require_project(directory)
    if kind == ProjectKind.PIXI:
        if bootstrap_lock:
            if not _run_pixi_install(directory, allow_fail=True):
                (directory / "pixi.lock").unlink(missing_ok=True)
                run(["pixi", "lock"], cwd=directory, quiet=quiet)
        run(["pixi", "install"], cwd=directory, quiet=quiet)
    else:
        if bootstrap_lock:
            if not _run_uv_sync(directory, allow_fail=True):
                (directory / "uv.lock").unlink(missing_ok=True)
                run(["uv", "lock"], cwd=directory, quiet=quiet)
        run(["uv", "sync"], cwd=directory, quiet=quiet)


def _run_pixi_install(directory: Path, *, allow_fail: bool = False) -> bool:
    try:
        run(["pixi", "install"], cwd=directory, quiet=True)
        return True
    except LabError:
        if allow_fail:
            return False
        raise


def _run_uv_sync(directory: Path, *, allow_fail: bool = False) -> bool:
    try:
        run(["uv", "sync"], cwd=directory, quiet=True)
        return True
    except LabError:
        if allow_fail:
            return False
        raise


def write_manifest(path: Path, manifest: EnvManifest) -> None:
    path.write_text(manifest.model_dump_json(indent=2) + "\n")


def read_manifest(path: Path) -> EnvManifest:
    return EnvManifest.model_validate_json(path.read_text())


def save_env(name: str, save_dir: Path, source: Path, *, full: bool = False) -> Path:
    kind = require_project(source)
    save_dir.mkdir(parents=True, exist_ok=True)

    if kind == ProjectKind.PIXI:
        shutil.copy2(source / "pixi.toml", save_dir / "pixi.toml")
        if (source / "pixi.lock").is_file():
            shutil.copy2(source / "pixi.lock", save_dir / "pixi.lock")
        env_dir = ".pixi"
    else:
        shutil.copy2(source / "pyproject.toml", save_dir / "pyproject.toml")
        if (source / "uv.lock").is_file():
            shutil.copy2(source / "uv.lock", save_dir / "uv.lock")
        env_dir = ".venv"

    for extra in (".python-version", "README.md"):
        src = source / extra
        if src.is_file():
            shutil.copy2(src, save_dir / extra)

    manifest = EnvManifest(
        name=name,
        kind=kind,
        saved_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        saved_from=str(source.resolve()),
        user=os.environ.get("USER", "unknown"),
        full=full,
    )
    write_manifest(save_dir / "manifest.json", manifest)

    if full:
        src_env = source / env_dir
        if not src_env.is_dir():
            raise LabError(
                f"No {env_dir} directory to pack.",
                hint="Run pixi install or uv sync first.",
            )
        packed = save_dir / "env.tar.zst"
        from canfar_lab.core.workspace import tar_zst

        try:
            tar_zst(source / env_dir, packed, arcname=env_dir)
        except Exception as exc:
            raise LabError("Failed to compress environment pack") from exc

    return save_dir


def resolve_save_dir(name: str, save_root: Path, from_path: Path | None) -> Path:
    save_dir = from_path if from_path else save_root / name
    if not (save_dir / "manifest.json").is_file():
        raise LabError(
            f"Save not found: {save_dir}",
            hint="canfar-lab saves\n  canfar-lab env save " + name,
        )
    return save_dir


def list_saves(save_root: Path) -> list[tuple[Path, EnvManifest]]:
    if not save_root.is_dir():
        return []
    results: list[tuple[Path, EnvManifest]] = []
    for entry in sorted(save_root.iterdir()):
        manifest_path = entry / "manifest.json"
        if entry.is_dir() and manifest_path.is_file():
            results.append((entry, read_manifest(manifest_path)))
    return results


def save_rows(save_root: Path) -> list[dict[str, str]]:
    return [
        {
            "name": m.name,
            "kind": m.kind.value,
            "saved_at": m.saved_at,
            "path": str(entry),
            "full": str(m.full).lower(),
        }
        for entry, m in list_saves(save_root)
    ]


def warm_cache(save_dir: Path) -> None:
    manifest = read_manifest(save_dir / "manifest.json")
    with tempfile.TemporaryDirectory(prefix="canfar-lab-cache-") as tmp:
        tmp_path = Path(tmp)
        if manifest.kind == ProjectKind.PIXI:
            src_toml = save_dir / "pixi.toml"
            if not src_toml.is_file():
                return
            shutil.copy2(src_toml, tmp_path / "pixi.toml")
            lock = save_dir / "pixi.lock"
            if lock.is_file():
                shutil.copy2(lock, tmp_path / "pixi.lock")
            run(["pixi", "install", "--quiet"], cwd=tmp_path, quiet=True)
        else:
            src_proj = save_dir / "pyproject.toml"
            if not src_proj.is_file():
                return
            shutil.copy2(src_proj, tmp_path / "pyproject.toml")
            lock = save_dir / "uv.lock"
            if lock.is_file():
                shutil.copy2(lock, tmp_path / "uv.lock")
            run(["uv", "sync", "--quiet"], cwd=tmp_path, quiet=True)


def bootstrap_lock(save_dir: Path, project_dir: Path) -> bool:
    manifest = read_manifest(save_dir / "manifest.json")
    kind = detect_project(project_dir)
    if kind is None or kind != manifest.kind:
        return False

    if kind == ProjectKind.PIXI:
        if (project_dir / "pixi.lock").is_file():
            return False
        src = save_dir / "pixi.lock"
        if not src.is_file():
            return False
        shutil.copy2(src, project_dir / "pixi.lock")
        return True

    if (project_dir / "uv.lock").is_file():
        return False
    src = save_dir / "uv.lock"
    if not src.is_file():
        return False
    shutil.copy2(src, project_dir / "uv.lock")
    return True


def restore_env(save_dir: Path, target: Path) -> None:
    manifest = read_manifest(save_dir / "manifest.json")
    target.mkdir(parents=True, exist_ok=True)

    for name in (
        "pixi.toml",
        "pixi.lock",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "README.md",
    ):
        src = save_dir / name
        if src.is_file():
            shutil.copy2(src, target / name)

    packed = save_dir / "env.tar.zst"
    if manifest.full and packed.is_file():
        zstd = subprocess.Popen(["zstd", "-d", "-c", str(packed)], stdout=subprocess.PIPE)
        try:
            subprocess.run(["tar", "-xf", "-"], cwd=target, stdin=zstd.stdout, check=True)
        finally:
            if zstd.stdout:
                zstd.stdout.close()
            zstd.wait()
            if zstd.returncode not in (0, None):
                raise LabError("Failed to decompress full environment pack")
    else:
        install_project(target)


def format_dir_size(path: Path) -> str:
    from canfar_lab.core.storage import dir_size

    size = dir_size(path)
    if size == 0:
        return "0 B"
    return humanize.naturalsize(size, binary=True)


def init_project(target: Path, *, use_uv: bool = False) -> ProjectKind:
    target.mkdir(parents=True, exist_ok=True)
    if use_uv:
        run(["uv", "init", "--no-readme"], cwd=target)
        return ProjectKind.UV
    run(["pixi", "init", "--no-progress"], cwd=target)
    return ProjectKind.PIXI
