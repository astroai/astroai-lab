from __future__ import annotations

from typer.testing import CliRunner

from astroai_lab.cli.main import app

runner = CliRunner()


def test_notebook_starter_copies(tmp_path) -> None:
    result = runner.invoke(app, ["notebook", "starter", "--to", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "starter.ipynb").is_file()


def test_notebook_starter_marimo(tmp_path) -> None:
    result = runner.invoke(app, ["notebook", "starter", "marimo", "--to", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "starter.py").is_file()
    text = (tmp_path / "starter.py").read_text()
    assert "import marimo" in text
    assert "astroai-lab" in text
    assert "<div" not in text
    assert "Session status" in text
    assert "vospace_controls" in text or "VOSpaceUI" in text
    assert "Open an existing project" in text
    assert 'check_output(["astroai-lab", "doctor"' not in text


def test_notebook_starter_unknown(tmp_path) -> None:
    result = runner.invoke(app, ["notebook", "starter", "nope", "--to", str(tmp_path)])
    assert result.exit_code == 1
