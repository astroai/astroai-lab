from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from canfar_lab.cli.main import app
from canfar_lab.config.settings import get_settings
from canfar_lab.core.git import git_init_and_commit, git_status
from canfar_lab.core.hygiene import apply_clean, collect_home_targets
from canfar_lab.core.project import save_env, save_rows
from canfar_lab.models.manifest import ProjectKind

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def lab_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_WORK_DIR", str(work))
    monkeypatch.chdir(work)
    return work


def _pixi_project(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname = "demo"\n')
    (path / "pixi.lock").write_text("lock-content")


def test_git_status_in_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    status = git_status(tmp_path)
    assert status.in_repo is True


def test_git_init_and_commit(tmp_path: Path) -> None:
    repo = tmp_path / "newrepo"
    repo.mkdir()
    (repo / "README.md").write_text("hi")
    with patch("canfar_lab.utils.subprocess.run") as mock_run:
        git_init_and_commit(repo)
    assert mock_run.call_count >= 3


def test_save_env_creates_manifest(lab_env: Path) -> None:
    project = lab_env / "mylab"
    _pixi_project(project)
    save_root = lab_env / "saves"
    save_root.mkdir()
    save_env("mylab", save_root / "mylab", project)
    manifest = save_root / "mylab" / "manifest.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text())
    assert data["kind"] == ProjectKind.PIXI.value
    rows = save_rows(save_root)
    assert len(rows) == 1
    assert rows[0]["name"] == "mylab"


def test_push_skips_git_when_not_repo(lab_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = lab_env / "mylab"
    _pixi_project(project)
    monkeypatch.chdir(project)
    with patch("canfar_lab.core.git.git_status") as gs:
        gs.return_value = type("S", (), {"in_repo": False, "uncommitted": False})()
        with patch("canfar_lab.cli.init_clone_env.save_env") as save:
            result = runner.invoke(app, ["--yes", "push"])
    assert result.exit_code == 0
    save.assert_called_once()


def test_clean_home_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_WORK_DIR", str(tmp_path / "work"))
    cache = home / ".cache" / "pip"
    cache.mkdir(parents=True)
    (cache / "wheel").write_text("x")
    result = runner.invoke(app, ["--dry-run", "clean", "home", "--stale-pkg"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower()


def test_hygiene_collect_and_apply_dry_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cache = home / ".cache" / "pip"
    cache.mkdir(parents=True)
    (cache / "pkg").write_text("x" * 100)
    targets = collect_home_targets(home, stale_pkg=True, ml=False, hf=False, xdg_junk=False)
    assert targets
    freed = apply_clean(targets, dry_run=True)
    assert freed > 0
    assert cache.exists()


def test_data_stage_missing_source(lab_env: Path) -> None:
    result = runner.invoke(app, ["data", "stage", "/no/such/path"])
    assert result.exit_code == 1


def test_status_command(lab_env: Path) -> None:
    with patch("canfar_lab.cli.status.df_line", return_value=None):
        with patch("canfar_lab.cli.status.list_arc_projects", return_value=[]):
            with patch("canfar_lab.cli.status.home_breakdown", return_value=[]):
                with patch("canfar_lab.cli.status.top_cpu_processes", return_value=[]):
                    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_banner_json(lab_env: Path) -> None:
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "work_dir" in data
