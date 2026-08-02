"""Golden CLI contract for `astroai-lab agent` (Phase 0, docs/agent-rethink-plan.md).

Pins the exact registered verb surface so accidental growth (or premature
removal) fails loudly, and checks the Phase 0 alias mapping:

    report   → status --json
    interact → status --endpoints
    clean    → fix-config --clean
    fix      → fix-config

The deprecated aliases are hidden from help but must keep working and emit a
hint pointing at the new verb.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from astroai_lab.cli.agent_cmd import agent_app
from astroai_lab.cli.main import app

runner = CliRunner()

# Canonical surface (skills/models are sub-typers, not commands). Phase 2
# added `remove` (uninstall binary + config).
CANONICAL_VERBS = {
    "catalog",
    "list",
    "install",
    "remove",
    "setup",
    "update",
    "addons",
    "add",
    "skills",
    "project",
    "status",
    "verify",
    "fix-config",
    "models",
}
# Deprecated aliases kept for one release (hidden from help output).
DEPRECATED_ALIASES = {"fix", "clean", "report", "interact"}


def _registered_names() -> set[str]:
    names = {c.name for c in agent_app.registered_commands}
    names |= {g.name for g in agent_app.registered_groups}
    return names


def test_agent_verb_surface_pinned() -> None:
    """The registered surface must be exactly canonical + deprecated aliases."""
    assert _registered_names() == CANONICAL_VERBS | DEPRECATED_ALIASES


def test_agent_help_lists_every_canonical_verb() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    for verb in CANONICAL_VERBS:
        assert verb in out


def test_deprecated_aliases_hidden_from_help() -> None:
    """Deprecated aliases stay registered but are hidden from `--help`."""
    by_name = {c.name: c for c in agent_app.registered_commands}
    for alias in DEPRECATED_ALIASES:
        cmd = by_name[alias]
        assert getattr(cmd, "hidden", False), f"{alias} must be hidden from help"


def test_fix_clean_aliases_delegate(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    new_clean = runner.invoke(app, ["--json", "--dry-run", "agent", "fix-config", "--clean"])
    old_clean = runner.invoke(app, ["--json", "--dry-run", "agent", "clean"])
    assert new_clean.exit_code == 0
    assert old_clean.exit_code == 0
    assert "deprecated" in (old_clean.stdout + old_clean.stderr).lower()
    assert json.loads(new_clean.stdout) == json.loads(old_clean.stdout)

    new_fix = runner.invoke(app, ["--json", "--dry-run", "agent", "fix-config"])
    old_fix = runner.invoke(app, ["--json", "--dry-run", "agent", "fix"])
    assert new_fix.exit_code == 0
    assert old_fix.exit_code == 0
    assert "deprecated" in (old_fix.stdout + old_fix.stderr).lower()
    assert json.loads(new_fix.stdout) == json.loads(old_fix.stdout)


def test_status_endpoints_equals_interact(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    new = runner.invoke(app, ["--json", "agent", "status", "--endpoints"])
    old = runner.invoke(app, ["--json", "agent", "interact"])
    assert new.exit_code == 0
    assert old.exit_code == 0
    assert "deprecated" in (old.stdout + old.stderr).lower()
    assert json.loads(new.stdout) == json.loads(old.stdout)


def test_report_equals_status_json(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    new = runner.invoke(app, ["--json", "agent", "status"])
    old = runner.invoke(app, ["agent", "report"])
    assert new.exit_code == 0
    # report exits 1 when the setup report is not ok (same body as status --json)
    assert old.exit_code in (0, 1)
    assert "deprecated" in (old.stdout + old.stderr).lower()
    a = json.loads(new.stdout)
    b = json.loads(old.stdout)
    # `resources` (live memory %) and `log_tail` are time-varying between the
    # two separate invocations — compare the deterministic report body only.
    for doc in (a, b):
        doc.pop("resources", None)
        doc.pop("log_tail", None)
    assert a == b
