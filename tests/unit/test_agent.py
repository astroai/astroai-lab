from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from canfar_lab.agent.bundles import install_file, list_bundles, verify_setup
from canfar_lab.agent.setup import agent_setup
from canfar_lab.cli.main import app

runner = CliRunner()


def test_bundle_root_exists() -> None:
    from canfar_lab.agent.bundle_path import bundle_root

    assert (bundle_root() / "manifest.json").is_file()


def test_list_bundles() -> None:
    bundles = list_bundles()
    assert "cursor" in bundles
    assert "all" in bundles


def test_install_file(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("x")
    assert install_file(src, dst, force=False, dry_run=False)
    assert dst.read_text() == "x"


def test_agent_setup_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    agent_setup(bundles=["cli"], dry_run=True)
    assert not (home / ".config" / "canfar" / "lab" / "agent-env.sh").is_file()


def test_agent_verify_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    issues = verify_setup(home)
    assert issues


def test_agent_install_list() -> None:
    result = runner.invoke(app, ["agent", "install", "--list"])
    assert result.exit_code == 0
    assert "claude" in result.stdout


def test_agent_setup_cli_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "setup", "cli"])
    assert result.exit_code == 0


def test_install_tool_unknown() -> None:
    from canfar_lab.agent.install import install_tool
    from canfar_lab.errors import LabError

    with pytest.raises(LabError, match="Unknown tool"):
        install_tool("not-a-tool")


def test_install_tool_dry_run() -> None:
    from canfar_lab.agent.install import install_tool

    install_tool("node", dry_run=True)


def test_merge_mcp_servers(tmp_path: Path) -> None:
    from canfar_lab.agent.bundles import merge_mcp_servers

    src = tmp_path / "src.json"
    dst = tmp_path / "dst.json"
    src.write_text('{"mcpServers": {"a": {"url": "x"}}}')
    merge_mcp_servers(src, dst, force=True, dry_run=False)
    assert dst.is_file()

