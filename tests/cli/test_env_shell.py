from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from astroai_lab.cli.main import app


def test_env_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TMP_SRC_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["env", "export", "--no-ensure"])
    assert result.exit_code == 0
    assert "ASTROAI_LAB_BIN_DIR" in result.stdout


def test_env_install_shell(tmp_path: Path) -> None:
    dest = tmp_path / "shell"
    runner = CliRunner()
    result = runner.invoke(app, ["env", "install-shell", str(dest)])
    assert result.exit_code == 0
    assert (dest / "profile.sh").is_file()
    assert (dest / "hooks.sh").is_file()
