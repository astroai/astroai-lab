from __future__ import annotations

from pathlib import Path

import pytest

from astroai_lab.agent.free_models import (
    DEFAULT_PRESET,
    apply_codex,
    apply_free_models,
    apply_goose,
    apply_kilo,
    apply_opencode,
    list_presets,
)


def test_list_presets() -> None:
    presets = list_presets()
    assert DEFAULT_PRESET in presets
    assert "openrouter" in presets["coding"]


def test_apply_kilo_dry_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert apply_kilo(home, "coding", force=False, dry_run=True)
    assert not (home / ".config" / "kilo" / "kilo.jsonc").exists()


def test_apply_kilo_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert apply_kilo(home, "coding", force=False, dry_run=False)
    cfg = home / ".config" / "kilo" / "kilo.jsonc"
    assert cfg.is_file()
    assert "kilo-auto/free" in cfg.read_text()


def test_apply_goose_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert apply_goose(home, "coding", force=False, dry_run=False)
    text = (home / ".config" / "goose" / "config.yaml").read_text()
    assert "GOOSE_PROVIDER: openrouter" in text
    assert "qwen/qwen3-coder:free" in text


def test_apply_opencode_merges(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cfg_dir = home / ".config" / "opencode"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "opencode.json").write_text('{"mcp": {"x": {}}}')
    assert apply_opencode(home, "coding", force=False, dry_run=False)
    data = __import__("json").loads((cfg_dir / "opencode.json").read_text())
    assert data["model"].startswith("openrouter/")
    assert "mcp" in data


def test_apply_codex_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert apply_codex(home, "coding", force=False, dry_run=False)
    text = (home / ".codex" / "config.toml").read_text()
    assert 'model_provider = "openrouter"' in text


def test_apply_free_models_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    actions = apply_free_models(home=home, dry_run=True, skip_cline=True)
    assert actions
    assert not (home / ".config" / "kilo" / "kilo.jsonc").exists()


def test_agent_models_list_cli() -> None:
    from typer.testing import CliRunner

    from astroai_lab.cli.main import app

    result = CliRunner().invoke(app, ["agent", "models", "list"])
    assert result.exit_code == 0
    assert "coding" in result.stdout


def test_agent_install_list_includes_kilo_cline() -> None:
    from typer.testing import CliRunner

    from astroai_lab.cli.main import app

    result = CliRunner().invoke(app, ["agent", "install", "--list"])
    assert result.exit_code == 0
    assert "kilo" in result.stdout
    assert "cline" in result.stdout
    assert "goose" in result.stdout


def test_apply_free_models_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    actions = apply_free_models(home=home, skip_cline=True, dry_run=False)
    assert (home / ".config" / "kilo" / "kilo.jsonc").is_file()
    assert (home / ".config" / "canfar" / "lab" / "openrouter.env.example").is_file()
    assert actions


def test_agent_models_free_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from astroai_lab.cli.main import app

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = CliRunner().invoke(app, ["--dry-run", "agent", "models", "free"])
    assert result.exit_code == 0
    assert "kilo" in (result.stdout + result.stderr + getattr(result, "output", ""))


def test_agent_models_guide() -> None:
    from typer.testing import CliRunner

    from astroai_lab.cli.main import app

    result = CliRunner().invoke(app, ["agent", "models"])
    assert result.exit_code == 0
    assert "OpenRouter" in result.stdout
