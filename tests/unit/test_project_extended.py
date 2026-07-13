from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from astroai_lab.core.project import (
    format_dir_size,
    install_project,
    read_manifest,
    require_project,
    resolve_save_dir,
    restore_env,
    save_env,
    warm_cache,
    write_manifest,
)
from astroai_lab.errors import LabError
from astroai_lab.models.manifest import EnvManifest, ProjectKind


def _pixi(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname = "p"\n')
    (path / "pixi.lock").write_text("lock")


def _uv(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text('[project]\nname = "p"\n')
    (path / "uv.lock").write_text("lock")


def test_require_project_raises(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="No pixi or uv"):
        require_project(tmp_path)


def test_resolve_save_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="Save not found"):
        resolve_save_dir("missing", tmp_path, None)


def test_format_dir_size(tmp_path: Path) -> None:
    assert format_dir_size(tmp_path / "nope") == "0 B"
    d = tmp_path / "data"
    d.mkdir()
    (d / "f").write_text("hello")
    assert "B" in format_dir_size(d)


def test_write_and_read_manifest(tmp_path: Path) -> None:
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="20260101T000000Z",
        saved_from="/x",
        user="u",
    )
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    loaded = read_manifest(path)
    assert loaded.name == "t"


def test_save_env_uv_project(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _uv(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    assert (save_dir / "pyproject.toml").is_file()
    assert (save_dir / "manifest.json").is_file()


def test_save_env_full_requires_env_dir(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    with pytest.raises(LabError, match="No .pixi"):
        save_env("proj", tmp_path / "save", project, full=True)


def test_save_env_full_packs(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    env_dir = project / ".pixi"
    env_dir.mkdir()
    (env_dir / "dummy").write_text("x")

    mock_tar = MagicMock()
    mock_tar.stdout = b"tar-data"
    mock_tar.returncode = 0

    mock_zstd = MagicMock()
    mock_zstd.stdin = MagicMock()
    mock_zstd.returncode = 0

    with patch("astroai_lab.core.project.subprocess.run", return_value=mock_tar):
        with patch("astroai_lab.core.project.subprocess.Popen", return_value=mock_zstd):
            save_env("proj", tmp_path / "save", project, full=True)
    assert (tmp_path / "save" / "env.tar.zst").exists()


def test_restore_env_installs_when_not_full(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    dest = tmp_path / "restored"
    with patch("astroai_lab.core.project.install_project") as install:
        restore_env(save_dir, dest)
    install.assert_called_once_with(dest)


def test_restore_env_full_unpacks(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project, full=False)
    manifest = read_manifest(save_dir / "manifest.json")
    manifest.full = True
    write_manifest(save_dir / "manifest.json", manifest)
    (save_dir / "env.tar.zst").write_bytes(b"fake")

    mock_zstd = MagicMock()
    mock_zstd.stdout = MagicMock()
    mock_zstd.returncode = 0
    with patch("astroai_lab.core.project.subprocess.Popen", return_value=mock_zstd):
        with patch("astroai_lab.core.project.subprocess.run") as mock_run:
            restore_env(save_dir, tmp_path / "dest")
    mock_run.assert_called_once()


def test_install_project_pixi(tmp_path: Path) -> None:
    _pixi(tmp_path)
    with patch("astroai_lab.core.project.run") as mock_run:
        install_project(tmp_path)
    mock_run.assert_called_with(["pixi", "install"], cwd=tmp_path, quiet=False)


def test_install_project_uv_bootstrap(tmp_path: Path) -> None:
    _uv(tmp_path)
    with patch("astroai_lab.core.project._run_uv_sync", return_value=False):
        with patch("astroai_lab.core.project.run") as mock_run:
            install_project(tmp_path, bootstrap_lock=True)
    assert mock_run.call_count >= 2


def test_warm_cache_pixi(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    _pixi(save_dir)
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    write_manifest(save_dir / "manifest.json", manifest)
    with patch("astroai_lab.core.project.run") as mock_run:
        warm_cache(save_dir)
    mock_run.assert_called_once()


def test_warm_cache_uv(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    _uv(save_dir)
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.UV,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    write_manifest(save_dir / "manifest.json", manifest)
    with patch("astroai_lab.core.project.run") as mock_run:
        warm_cache(save_dir)
    mock_run.assert_called_once()


def test_init_project_mocked(tmp_path: Path) -> None:
    from astroai_lab.core.project import init_project

    target = tmp_path / "new"
    with patch("astroai_lab.core.project.run") as mock_run:
        kind = init_project(target, use_uv=True)
    assert kind == ProjectKind.UV
    mock_run.assert_called_once()
