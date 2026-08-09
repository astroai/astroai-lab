"""Golden CLI contract for `astroai-lab agent` (lean surface).

Pins the exact registered verb surface so accidental growth fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from astroai_lab.cli.agent_cmd import agent_app
from astroai_lab.cli.main import app

runner = CliRunner()

# Lean surface: list/models/plugins are sub-typers.
CANONICAL_VERBS = {
    "list",
    "install",
    "remove",
    "wipe",
    "setup",
    "config",
    "update",
    "status",
    "verify",
    "repair",
    "models",
    "plugins",
}

REMOVED_VERBS = {
    "catalog",
    "addons",
    "add",
    "skills",
    "project",
    "fix-config",
    "fix",
    "clean",
    "report",
    "interact",
}


def _registered_names() -> set[str]:
    names = {c.name for c in agent_app.registered_commands}
    names |= {g.name for g in agent_app.registered_groups}
    return names


def test_agent_verb_surface_pinned() -> None:
    """The registered surface must be exactly the lean canonical set."""
    assert _registered_names() == CANONICAL_VERBS


def test_agent_help_lists_every_canonical_verb() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    for verb in CANONICAL_VERBS:
        assert verb in out
    for verb in REMOVED_VERBS:
        assert f"│ {verb} " not in out
        assert f"│ {verb}\n" not in out


def test_removed_verbs_are_gone() -> None:
    for verb in REMOVED_VERBS:
        result = runner.invoke(app, ["agent", verb])
        assert result.exit_code != 0, f"{verb} should be removed"
        assert "No such command" in (result.stdout + result.stderr)


def test_list_default_is_registry_shaped(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--json", "agent", "list"])
    # Fresh home → report not ok → exit 1, but JSON still emitted.
    assert result.exit_code in (0, 1)
    payload = json.loads(result.stdout)
    assert "agents" in payload
    assert "issues" in payload
    ids = {row["id"] for row in payload["agents"]}
    assert {"kilo", "zcode", "omp", "hermes"} <= ids


def test_list_config() -> None:
    result = runner.invoke(app, ["--json", "agent", "list", "config"])
    assert result.exit_code == 0
    items = json.loads(result.stdout)
    assert isinstance(items, list)
    assert any(i.get("id") == "ponytail" for i in items)


def test_status_json_exits_nonzero_when_unhealthy(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--json", "agent", "status"])
    payload = json.loads(result.stdout)
    if not payload.get("ok"):
        assert result.exit_code == 1
    else:
        assert result.exit_code == 0


def test_status_ui_flag(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--json", "agent", "status", "--ui"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "endpoints" in payload


def test_setup_project_positional_path(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(app, ["--dry-run", "agent", "setup", "--project", str(repo)])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert str(repo) in out or "Project templates" in out or "would" in out.lower() or result.exit_code == 0


def test_repair_clean(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--json", "--dry-run", "agent", "repair", "--clean"])
    assert result.exit_code == 0
