from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from canfar_lab.core.workspace import restore_workspace, save_workspace
from canfar_lab.errors import LabError


def _pixi(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname="p"\n')


def test_save_workspace(tmp_path: Path) -> None:
    work = tmp_path / "work"
    project = work / "mylab"
    _pixi(project)

    mock_tar = MagicMock()
    mock_tar.stdout = b"data"
    mock_zstd = MagicMock()
    mock_zstd.stdin = MagicMock()
    mock_zstd.returncode = 0

    with patch("canfar_lab.core.workspace.subprocess.run", return_value=mock_tar):
        with patch("canfar_lab.core.workspace.subprocess.Popen", return_value=mock_zstd):
            bundle = save_workspace(project, work, "mylab")
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "project.tar.zst").exists()


def test_save_workspace_with_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "work"
    project = work / "mylab"
    _pixi(project)
    cache = tmp_path / "uv-cache"
    cache.mkdir()
    monkeypatch.setenv("UV_CACHE_DIR", str(cache))

    mock_tar = MagicMock()
    mock_tar.stdout = b"data"
    mock_zstd = MagicMock()
    mock_zstd.stdin = MagicMock()
    mock_zstd.returncode = 0

    with patch("canfar_lab.core.workspace.subprocess.run", return_value=mock_tar):
        with patch("canfar_lab.core.workspace.subprocess.Popen", return_value=mock_zstd):
            with patch("canfar_lab.core.workspace.tar_zst") as mock_cache_tar:
                bundle = save_workspace(project, work, "mylab", with_cache=True)
    mock_cache_tar.assert_called_once()
    assert bundle.is_dir()


def test_restore_workspace(tmp_path: Path) -> None:
    work = tmp_path / "work"
    bundle = work / ".canfar-lab" / "workspaces" / "mylab"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text('{"name":"mylab"}')
    (bundle / "project.tar.zst").write_bytes(b"fake")

    mock_zstd = MagicMock()
    mock_zstd.stdout = MagicMock()
    mock_zstd.returncode = 0
    with patch("canfar_lab.core.workspace.subprocess.Popen", return_value=mock_zstd):
        with patch("canfar_lab.core.workspace.subprocess.run") as mock_run:
            dest = restore_workspace(work, "mylab")
    mock_run.assert_called_once()
    assert dest == work / "mylab"


def test_restore_workspace_missing_bundle(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="Workspace bundle not found"):
        restore_workspace(tmp_path, "missing")


def test_restore_workspace_missing_archive(tmp_path: Path) -> None:
    work = tmp_path / "work"
    bundle = work / ".canfar-lab" / "workspaces" / "mylab"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text("{}")
    with pytest.raises(LabError, match="Missing project archive"):
        restore_workspace(work, "mylab")
