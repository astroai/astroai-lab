"""Unit tests for agent catalog, clean state, auto-fix, and interact features."""

import json
from pathlib import Path

from typer.testing import CliRunner

from astroai_lab.agent.catalog import list_agent_catalog
from astroai_lab.agent.clean_agent import clean_agent_state
from astroai_lab.agent.fix import fix_agent_setup
from astroai_lab.agent.interact import inspect_interact_endpoints
from astroai_lab.cli.main import app

runner = CliRunner()


def test_catalog_basic(tmp_path: Path) -> None:
    catalog = list_agent_catalog(home=tmp_path)
    assert isinstance(catalog, list)
    assert len(catalog) > 0

    # Test filtering by kind
    containers = list_agent_catalog(kind="container", home=tmp_path)
    assert all(c["kind"] == "container" for c in containers)

    # Test filtering by tag
    lean_items = list_agent_catalog(tag="lean", home=tmp_path)
    assert all("lean" in [t.lower() for t in i["tags"]] for i in lean_items)

    # Test query search
    kilo_items = list_agent_catalog(query="kilo", home=tmp_path)
    assert any("kilo" in i["id"].lower() for i in kilo_items)


def test_clean_agent_state(tmp_path: Path) -> None:
    state_dir = tmp_path / ".astroai" / "lab"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_file = state_dir / "agent-setup.lock"
    failed_file = state_dir / "agent-setup-failed"
    log_file = state_dir / "agent-setup.log"
    lock_file.write_text("1234 1000", encoding="utf-8")
    failed_file.write_text("exit=1", encoding="utf-8")
    log_file.write_text("log content", encoding="utf-8")

    # Empty config file
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    empty_cfg = cursor_dir / "mcp.json"
    empty_cfg.write_text("{}", encoding="utf-8")

    # Test dry-run clean
    dry_results = clean_agent_state(home=tmp_path, logs=True, dry_run=True)
    assert any(r.status == "would_remove" for r in dry_results)

    # Test actual clean
    results = clean_agent_state(home=tmp_path, logs=True, dry_run=False)
    assert not lock_file.exists()
    assert not failed_file.exists()
    assert not log_file.exists()
    assert not empty_cfg.exists()
    assert len(results) >= 4


def test_fix_agent_setup(tmp_path: Path) -> None:
    # Create corrupted JSON file and missing dirs
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    mcp_file = cursor_dir / "mcp.json"
    mcp_file.write_text("{ broken json: ", encoding="utf-8")

    # Failed marker
    state_dir = tmp_path / ".astroai" / "lab"
    state_dir.mkdir(parents=True, exist_ok=True)
    failed_file = state_dir / "agent-setup-failed"
    failed_file.write_text("error", encoding="utf-8")

    # Test dry-run fix
    dry_results = fix_agent_setup(home=tmp_path, dry_run=True)
    assert len(dry_results) > 0

    # Test actual fix
    results = fix_agent_setup(home=tmp_path, dry_run=False)
    assert mcp_file.is_file()
    assert not failed_file.exists()
    # Content should be repaired to valid JSON
    data = json.loads(mcp_file.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert any(r.fixed for r in results)


def test_inspect_interact_endpoints() -> None:
    info = inspect_interact_endpoints()
    assert "session_kind" in info
    assert "endpoints" in info
    assert isinstance(info["endpoints"], list)


def test_cli_agent_catalog() -> None:
    result = runner.invoke(app, ["--json", "agent", "catalog"])
    assert result.exit_code == 0
    assert "openresearch" in result.output

    res_tag = runner.invoke(app, ["agent", "catalog", "--tag", "lean"])
    assert res_tag.exit_code == 0


def test_cli_agent_awesome_alias_removed() -> None:
    """The `agent awesome` alias was removed (use `agent catalog`)."""
    result = runner.invoke(app, ["--json", "agent", "awesome"])
    assert result.exit_code != 0
    assert "No such command" in (result.stdout + result.stderr)


def test_cli_agent_clean() -> None:
    result = runner.invoke(app, ["--json", "agent", "clean"])
    assert result.exit_code == 0

    res_dry = runner.invoke(app, ["agent", "clean", "--dry-run"])
    assert res_dry.exit_code == 0


def test_cli_agent_fix() -> None:
    result = runner.invoke(app, ["--json", "agent", "fix"])
    assert result.exit_code == 0

    res_dry = runner.invoke(app, ["agent", "fix", "--dry-run"])
    assert res_dry.exit_code == 0


def test_cli_agent_interact() -> None:
    result = runner.invoke(app, ["--json", "agent", "interact"])
    assert result.exit_code == 0
    assert "endpoints" in result.output

    res_plain = runner.invoke(app, ["agent", "interact"])
    assert res_plain.exit_code == 0


def test_cli_agent_verify_fix() -> None:
    result = runner.invoke(app, ["agent", "verify", "--fix"])
    assert result.exit_code == 0 or result.exit_code == 1
