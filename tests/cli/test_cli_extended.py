from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from astroai_lab.cli.main import app
from astroai_lab.config.settings import get_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def lab_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    work = tmp_path / "work"
    scratch = tmp_path / "scratch"
    home.mkdir()
    work.mkdir()
    scratch.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("WORK", str(work))
    monkeypatch.setenv("SCRATCH", str(scratch))
    monkeypatch.chdir(work)
    return work


def _pixi(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname="p"\n')
    (path / "pixi.lock").write_text("lock")


def test_clone_requires_gh(lab_env: Path) -> None:
    with patch("astroai_lab.cli.init_clone_env.shutil.which", return_value=None):
        result = runner.invoke(app, ["clone", "org/repo"])
    assert result.exit_code == 1
    assert "gh" in result.output.lower()


def test_clone_from_without_env(lab_env: Path) -> None:
    with patch("astroai_lab.cli.init_clone_env.shutil.which", return_value="/usr/bin/gh"):
        result = runner.invoke(app, ["clone", "--from", "/tmp/save", "org/repo"])
    assert result.exit_code == 1


def test_clone_success(lab_env: Path) -> None:
    with (
        patch("astroai_lab.cli.init_clone_env.shutil.which", return_value="/usr/bin/gh"),
        patch("astroai_lab.utils.subprocess.run") as mock_run,
        patch("astroai_lab.core.project.detect_project", return_value=None),
    ):
        result = runner.invoke(app, ["clone", "org/repo"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_clone_with_from_env(
    lab_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home2"
    home.mkdir()
    save_dir = home / ".astroai" / "lab" / "saves" / "ml-base"
    save_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    get_settings.cache_clear()
    (save_dir / "pixi.toml").write_text('[project]\nname="b"\n')
    manifest = {
        "name": "ml-base",
        "kind": "pixi",
        "saved_at": "t",
        "saved_from": "/x",
        "user": "u",
        "full": False,
    }
    (save_dir / "manifest.json").write_text(json.dumps(manifest))
    (save_dir / "pixi.lock").write_text("lock")

    from astroai_lab.models.manifest import ProjectKind

    with (
        patch("astroai_lab.cli.init_clone_env.shutil.which", return_value="/usr/bin/gh"),
        patch("astroai_lab.utils.subprocess.run"),
        patch("astroai_lab.core.project.warm_cache"),
        patch("astroai_lab.core.project.detect_project", return_value=ProjectKind.PIXI),
        patch("astroai_lab.core.project.bootstrap_lock", return_value=True),
        patch("astroai_lab.core.project.install_project"),
    ):
        result = runner.invoke(app, ["clone", "--from-env", "ml-base", "org/repo"])
    assert result.exit_code == 0, result.output


def test_init_existing_dir(lab_env: Path) -> None:
    existing = lab_env / "taken"
    existing.mkdir()
    (existing / "file").write_text("x")
    result = runner.invoke(app, ["init", "taken"])
    assert result.exit_code == 1


def test_init_success(lab_env: Path) -> None:
    from astroai_lab.models.manifest import ProjectKind

    with (
        patch("astroai_lab.core.project.init_project", return_value=ProjectKind.PIXI),
        patch("astroai_lab.cli.init_clone_env.git_init_and_commit"),
    ):
        result = runner.invoke(app, ["init", "newlab", "--no-gh"])
    assert result.exit_code == 0


def test_resume_success(lab_env: Path, tmp_path: Path) -> None:
    save_dir = tmp_path / "saves" / "mylab"
    save_dir.mkdir(parents=True)
    (save_dir / "pixi.toml").write_text('[project]\nname="p"\n')
    manifest = {
        "name": "mylab",
        "kind": "pixi",
        "saved_at": "t",
        "saved_from": "/x",
        "user": "u",
        "full": False,
    }
    (save_dir / "manifest.json").write_text(json.dumps(manifest))

    with patch("astroai_lab.core.project.restore_env"):
        result = runner.invoke(app, ["resume", "mylab", "--from", str(save_dir)])
    assert result.exit_code == 0


def test_save_and_list_flat(lab_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = lab_env / "demo"
    _pixi(project)
    monkeypatch.chdir(project)
    result = runner.invoke(app, ["save", "demo"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["--json", "saves"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)


def test_resume_flat(lab_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saves = Path.home() / ".astroai" / "lab" / "saves" / "mylab"
    saves.mkdir(parents=True, exist_ok=True)
    (saves / "pixi.toml").write_text('[project]\nname="p"\n')
    manifest = {
        "name": "mylab",
        "kind": "pixi",
        "saved_at": "t",
        "saved_from": "/x",
        "user": "u",
        "full": False,
    }
    (saves / "manifest.json").write_text(json.dumps(manifest))
    get_settings.cache_clear()
    with patch("astroai_lab.core.project.restore_env"):
        result = runner.invoke(app, ["resume", "mylab"])
    assert result.exit_code == 0


def test_kernel_register_cli(lab_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = lab_env / "nb"
    project.mkdir()
    (project / "pixi.toml").write_text('[project]\nname="p"\n')
    py = project / ".pixi" / "envs" / "default" / "bin"
    py.mkdir(parents=True)
    (py / "python").write_text("#!/bin/sh")
    monkeypatch.chdir(project)
    with (
        patch("astroai_lab.core.kernel.shutil.which", return_value="/usr/bin/jupyter"),
        patch("astroai_lab.core.kernel.run"),
    ):
        result = runner.invoke(app, ["kernel", "register"])
    assert result.exit_code == 0


def test_kernel_list_json(lab_env: Path) -> None:
    with patch("astroai_lab.cli.kernel.list_kernels", return_value=[{"name": "k", "path": "/p"}]):
        for argv in (["--json", "kernel", "list"], ["kernel", "list", "--json"]):
            result = runner.invoke(app, argv)
            assert result.exit_code == 0, result.output
            data = json.loads(result.stdout)
            assert data[0]["name"] == "k"


def test_config_show_human(lab_env: Path) -> None:
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "default_pm" in result.output


def test_agent_list_human(lab_env: Path) -> None:
    result = runner.invoke(app, ["agent", "list"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "bin" in out and "cfg" in out


def test_agent_list_json(lab_env: Path) -> None:
    result = runner.invoke(app, ["--json", "agent", "list"])
    # Fresh / incomplete setup → ok:false → exit 1; JSON still emitted.
    assert result.exit_code in (0, 1)
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) > 0
    assert "agent" in data["agents"][0]
    assert "ok" in data
    assert "issues" in data


def test_banner_with_project(lab_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = lab_env / "active"
    _pixi(project)
    monkeypatch.chdir(project)
    with patch("astroai_lab.cli.banner.git_status") as gs:
        gs.return_value = type("S", (), {"in_repo": True, "uncommitted": True})()
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "uncommitted" in result.output.lower() or "save" in result.output.lower()
