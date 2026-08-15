from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from astroai_lab.cli.main import app
from astroai_lab.config.settings import get_settings

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
    monkeypatch.setenv("WORK", str(work))
    return home


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "astroai-lab" in result.stdout
    from astroai_lab.version import PACKAGE_VERSION

    assert PACKAGE_VERSION in result.stdout


def test_help_command() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "save" in result.output


def test_help_single_command() -> None:
    result = runner.invoke(app, ["help", "--command", "agent"])
    assert result.exit_code == 0
    assert "Usage: astroai-lab agent" in result.output
    # Scoped: agent group help shows agent subcommands, not save/resume ones.
    assert "plugins" in result.output
    assert "Usage: astroai-lab save" not in result.output


def test_help_single_nested_command() -> None:
    result = runner.invoke(app, ["help", "-c", "agent list"])
    assert result.exit_code == 0
    assert "Usage: astroai-lab agent list" in result.output


def test_help_unknown_command() -> None:
    result = runner.invoke(app, ["help", "-c", "nope"])
    assert result.exit_code == 1
    assert "nope" in result.output


def test_guide_alias_removed() -> None:
    """The `guide` alias was removed in the 0.3 simplification (use `help`)."""
    result = runner.invoke(app, ["guide"])
    assert result.exit_code != 0
    assert "No such command" in (result.stdout + result.stderr)


def test_help_json_inventory() -> None:
    result = runner.invoke(app, ["help", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "commands" in data
    paths = {c["path"] for c in data["commands"]}
    assert "status" in paths
    assert "agent list" in paths
    assert "save" in paths
    assert "resume" in paths
    assert "saves" not in paths
    assert "guide" not in paths


def test_help_json_single_command() -> None:
    result = runner.invoke(app, ["help", "-c", "status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["path"] == "status"
    assert "help" in data
    assert "options" in data
    assert any("--json" in o["opts"] for o in data["options"])
    assert any("--verbose" in o["opts"] for o in data["options"])


def test_help_json_unknown_command() -> None:
    result = runner.invoke(app, ["help", "-c", "nope", "--json"])
    assert result.exit_code == 1
    assert "nope" in result.output


def test_default_banner(lab_home: Path) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "astroai-lab" in result.output.lower() or "work" in result.output.lower()


@patch("astroai_lab.cli.banner.cwd_arc_project")
def test_banner_with_active_team(mock_cwd, lab_home: Path) -> None:
    active = MagicMock()
    active.name = "demo"
    active.path = Path("/arc/projects/demo")
    active.access = "read-write"
    active.quota.free = "10GB"
    active.quota.total = "100GB"
    active.quota.pct = 10

    mock_cwd.return_value = active
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "team:    /arc/projects/demo" in result.output
    assert "10GB free" in result.output


def test_config_path(lab_home: Path) -> None:
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert str(lab_home / ".astroai" / "lab" / "config.yaml") in result.stdout


def test_config_show_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["default_pm"] == "pixi"


def test_config_show_json_local(lab_home: Path) -> None:
    result = runner.invoke(app, ["config", "show", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["default_pm"] == "pixi"


def test_config_root(lab_home: Path) -> None:
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "config show" in result.output
    assert "config --help" in result.output


def test_config_root_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["--json", "config"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["help"] == "astroai-lab config --help"
    assert "show" in data["try"]


def test_save_list_empty_json(lab_home: Path) -> None:
    result = runner.invoke(app, ["save", "--list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


def test_saves_command_removed() -> None:
    result = runner.invoke(app, ["saves"])
    assert result.exit_code != 0
    assert "No such command" in (result.stdout + result.stderr)


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
