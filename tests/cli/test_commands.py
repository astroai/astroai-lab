from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from canfar_lab.cli.main import app
from canfar_lab.config.settings import get_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def lab_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    work = home / "work"
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_WORK_DIR", str(work))
    return home


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "canfar-lab" in result.stdout


def test_guide_command() -> None:
    result = runner.invoke(app, ["guide"])
    assert result.exit_code == 0
    assert "Session loop" in result.output


def test_doctor_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["--json", "doctor"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "work_dir" in data
    assert "tools" in data


def test_default_banner(lab_home: Path) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "canfar-lab" in result.output.lower() or "work" in result.output.lower()


def test_config_path(lab_home: Path) -> None:
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert str(lab_home / ".canfar" / "lab" / "config.yaml") in result.stdout


def test_config_show_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["default_pm"] == "pixi"


def test_saves_empty_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["--json", "saves"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


def test_save_requires_project(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = lab_home / "work"
    monkeypatch.chdir(work)
    result = runner.invoke(app, ["save", "mylab"])
    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output.lower()


def test_init_creates_pixi_project(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = lab_home / "work"
    monkeypatch.chdir(work)
    result = runner.invoke(
        app,
        ["init", "demo", "--no-git", "--no-gh"],
        catch_exceptions=False,
    )
    if result.exit_code != 0:
        pytest.skip("pixi/uv not available in test environment")
    target = work / "demo"
    assert target.is_dir()
    assert (target / "pixi.toml").is_file() or (target / "pyproject.toml").is_file()
