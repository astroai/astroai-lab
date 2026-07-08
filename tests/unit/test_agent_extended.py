from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from canfar_lab.agent.bundle_path import bundle_root
from canfar_lab.agent.bundles import (
    ensure_agent_dirs,
    install_goose_config,
    install_upstream_skills,
    list_github_sources,
    merge_claude_json,
    merge_opencode_mcp,
    run_bundle,
    update_github_source,
    write_stamp,
)
from canfar_lab.cli.main import app

runner = CliRunner()


def test_ensure_agent_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    ensure_agent_dirs(home, dry_run=False)
    assert (home / ".cursor" / "rules").is_dir()


def test_write_stamp(tmp_path: Path) -> None:
    home = tmp_path / "home"
    write_stamp(home, "install", dry_run=False)
    assert (home / ".canfar" / "lab" / "agent-setup-stamp").is_file()


def test_run_bundle_cli_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    root = bundle_root()
    run_bundle("cli", root, home, None, force=False, dry_run=True)


def test_merge_claude_and_opencode(tmp_path: Path) -> None:
    src = tmp_path / "src.json"
    dst = tmp_path / "dst.json"
    src.write_text('{"mcpServers": {"x": {}}}')
    merge_claude_json(src, dst, force=True, dry_run=False)
    assert dst.is_file()
    op_src = tmp_path / "op.json"
    op_dst = tmp_path / "op_dst.json"
    op_src.write_text('{"mcp": {"a": {}}, "lsp": {}}')
    merge_opencode_mcp(op_src, op_dst, force=True, dry_run=False)
    assert op_dst.is_file()


def test_install_goose_config(tmp_path: Path) -> None:
    root = bundle_root()
    home = tmp_path / "home"
    install_goose_config(root, home, force=True, dry_run=False)
    assert (home / ".config" / "goose" / "config.yaml").is_file()


def test_install_upstream_skills_dry_run() -> None:
    root = bundle_root()
    home = Path("/tmp/unused")
    count = install_upstream_skills(root, home, force=False, dry_run=True)
    assert count >= 0


def test_agent_project_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.chdir(project)
    result = runner.invoke(app, ["--dry-run", "agent", "project"])
    assert result.exit_code == 0


def test_project_init_cli_no_arc() -> None:
    result = runner.invoke(app, ["project", "init", "mygroup"])
    assert result.exit_code == 1


def test_list_github_sources() -> None:
    sources = list_github_sources()
    assert any(s["name"] == "ast-grep" for s in sources)


def test_update_github_source_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = update_github_source(
        home,
        "ast-grep",
        "ast-grep/agent-skill",
        "ast-grep/skills/ast-grep",
        force=True,
        dry_run=True,
    )
    assert result.status == "dry-run"


def test_agent_sources_list_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["agent", "sources", "list"])
    assert result.exit_code == 0
    assert "ast-grep" in (result.stdout + result.stderr)


def test_agent_sync_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "sync"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "refreshed skill" in out or "would refresh skill" in out


def test_agent_sources_update_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "sources", "update"])
    assert result.exit_code == 0
    assert "ast-grep" in (result.stdout + result.stderr)
