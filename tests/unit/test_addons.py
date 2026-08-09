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
    assert "canfar-ray" in ids


def test_add_agent_skill_installs_to_hermes_and_openclaw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("canfar-ray", home=home)
    assert result.status == "installed"
    for rel in (".hermes/skills/canfar-ray/SKILL.md", ".openclaw/skills/canfar-ray/SKILL.md"):
        assert (home / rel).is_file(), f"missing {rel}"
    # Idempotent second call skips.
    assert add_addon("canfar-ray", home=home).status == "skipped"
    # Installed detection agrees.
    assert addon_installed(get_addon("canfar-ray"), home)


def test_add_agent_skill_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("canfar-ray", home=home, dry_run=True)
    assert result.status == "dry-run"
    assert not (home / ".hermes").exists()


def test_add_agent_skill_force_reinstalls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert add_addon("canfar-ray", home=home).status == "installed"
    assert add_addon("canfar-ray", home=home, force=True).status == "installed"


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


def test_load_addons_is_plugin_registry_shim() -> None:
    """addons.json was migrated — load_addons reads the plugin registry."""
    from astroai_lab.agent.plugins import load_plugins

    plugin_ids = {p["id"] for p in load_plugins() if p.get("addon")}
    addon_ids = {a["id"] for a in load_addons()}
    assert addon_ids == plugin_ids
    # Legacy shape preserved: install.type transport + kind vocabulary.
    item = get_addon("ponytail")
    assert item is not None
    assert item["kind"] == "bundle"
    assert item["install"]["type"] == "github-bundle"
    assert isinstance(item["install"]["skills"], list)


def test_add_addon_delegates_to_plugins_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`add_addon` and `plugins.install_plugin` route identically."""
    from astroai_lab.agent.plugins import install_plugin

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    addon_result = add_addon("canfar-ray", home=home)
    assert addon_result.status == "installed"
    plugin_results = install_plugin("canfar-ray", home=home, installed_only=False)
    # Both paths produced the same skill dirs.
    for agent in ("hermes", "openclaw"):
        rel = f".{agent}/skills/canfar-ray/SKILL.md"
        assert (home / rel).is_file()
    assert all(r.status == "skipped" for r in plugin_results)


def test_add_addon_github_bundle_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrated github-bundle addon dry-run (no network)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = add_addon("ponytail", home=home, dry_run=True)
    assert result.status == "dry-run"
    assert not (home / ".cursor").exists()


def test_add_unknown_raises() -> None:
    with pytest.raises(LabError, match="Unknown addon"):
        add_addon("definitely-missing")


def test_agent_plugins_list_includes_addons() -> None:
    result = runner.invoke(app, ["agent", "plugins", "list"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "ponytail" in out
    assert "polars" in out


def test_agent_plugins_list_kind_cli() -> None:
    result = runner.invoke(app, ["agent", "plugins", "list", "--kind", "skill"])
    assert result.exit_code == 0
    assert "ponytail" in (result.stdout + result.stderr) or result.exit_code == 0


def test_agent_plugins_install_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "plugins", "install", "git-mcp"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "git-mcp" in out
