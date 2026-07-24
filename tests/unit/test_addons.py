from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from astroai_lab.agent.addons import (
    add_addon,
    addon_installed,
    get_addon,
    list_addons,
    load_addons,
)
from astroai_lab.cli.main import app
from astroai_lab.errors import LabError

runner = CliRunner()


def test_load_addons_has_ponytail_and_polars() -> None:
    addons = load_addons()
    ids = {a["id"] for a in addons}
    assert "ponytail" in ids
    assert "polars" in ids
    assert "modern-python" in ids
    assert "git-mcp" in ids


def test_list_addons_filter_tag() -> None:
    lean = list_addons(tag="lean")
    assert any(r["id"] == "ponytail" for r in lean)
    science = list_addons(tag="science")
    assert any(r["id"] == "polars" for r in science)


def test_get_addon_unknown() -> None:
    assert get_addon("not-a-real-addon") is None


def test_add_bundled_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("token-efficient", home=home)
    assert result.status == "skipped"


def test_add_mcp_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("git-mcp", home=home, dry_run=True)
    assert result.status == "dry-run"


def test_add_mcp_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    (home / ".cursor" / "mcp.json").write_text('{"mcpServers": {}}\n')
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("git-mcp", home=home, force=True)
    assert result.status == "installed"
    data = (home / ".cursor" / "mcp.json").read_text()
    assert '"git"' in data
    assert addon_installed(get_addon("git-mcp"), home)


def test_add_mcp_refuses_corrupt_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    (home / ".cursor" / "mcp.json").write_text("{ not json\n")
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(LabError, match="unreadable"):
        add_addon("git-mcp", home=home, force=True)


def test_strip_jsonc_preserves_comma_in_string() -> None:
    from astroai_lab.utils.json_utils import parse_jsonc

    assert parse_jsonc('{"x": "hello,}", "y": 1}') == {"x": "hello,}", "y": 1}
    assert parse_jsonc('{"a": 1,}') == {"a": 1}


def test_add_unknown_raises() -> None:
    with pytest.raises(LabError, match="Unknown addon"):
        add_addon("definitely-missing")


def test_agent_addons_cli() -> None:
    result = runner.invoke(app, ["agent", "addons"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "ponytail" in out
    assert "polars" in out
    assert "not a list of agents" in out.lower() or "Curated addons" in out


def test_agent_addons_tag_cli() -> None:
    result = runner.invoke(app, ["agent", "addons", "--tag", "lean"])
    assert result.exit_code == 0
    assert "ponytail" in (result.stdout + result.stderr)


def test_agent_add_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "add", "git-mcp"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "git-mcp" in out
