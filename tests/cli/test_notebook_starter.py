from __future__ import annotations

from typer.testing import CliRunner

from astroai_lab.cli.main import app

runner = CliRunner()


def test_notebook_starter_copies(tmp_path) -> None:
    result = runner.invoke(app, ["notebook", "starter", "--to", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "starter.ipynb").is_file()
