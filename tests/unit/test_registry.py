"""Unit tests for the Phase 1 agent registry (docs/agent-rethink-plan.md).

Covers loader + schema validation, status detection, verify issues
(installed-only gating), install dispatch, and catalog/list integration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from astroai_lab.agent.catalog import list_agent_catalog
from astroai_lab.agent.registry import (
    get_registry_agent,
    install_registry_agent,
    load_registry,
    registry_agent_status,
    registry_ids,
    registry_verify_issues,
)
from astroai_lab.cli.main import app
from astroai_lab.errors import LabError

runner = CliRunner()


def _write_agent_yaml(root: Path, name: str, body: str) -> Path:
    agents = root / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    path = agents / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Loader + schema validation
# ---------------------------------------------------------------------------


def test_load_registry_hermes_openclaw() -> None:
    agents = load_registry()
    ids = [a["id"] for a in agents]
    assert "hermes" in ids
    assert "openclaw" in ids
    assert ids == sorted(ids)  # sorted by id


def test_load_registry_includes_migrated_agents() -> None:
    """kilo/goose/cline/opencode/codex migrated from install.TOOLS."""
    ids = {a["id"] for a in load_registry()}
    assert {"kilo", "goose", "cline", "opencode", "codex"} <= ids
    kilo = get_registry_agent("kilo")
    assert kilo is not None
    assert kilo["install"]["method"] == "curl"
    assert kilo["config"]["path"] == "~/.config/kilo/kilo.jsonc"
    codex = get_registry_agent("codex")
    assert codex is not None
    assert codex["install"]["method"] == "gh-release"
    assert "{arch}" in codex["install"]["asset"]


def test_load_registry_empty_dir(tmp_path: Path) -> None:
    assert load_registry(tmp_path) == []


def test_registry_ids_and_get(tmp_path: Path) -> None:
    assert "hermes" in registry_ids()
    assert get_registry_agent("openclaw") is not None
    assert get_registry_agent("not-an-agent") is None


def test_validation_missing_required_key(tmp_path: Path) -> None:
    _write_agent_yaml(
        tmp_path,
        "broken",
        "name: No ID\nhomepage: https://x\nbinary: x\ninstall:\n  method: npm\n  source: x\n",
    )
    with pytest.raises(LabError, match="missing required key"):
        load_registry(tmp_path)


def test_validation_bad_install_method(tmp_path: Path) -> None:
    _write_agent_yaml(
        tmp_path,
        "broken",
        "id: broken\nname: Broken\nhomepage: https://x\nbinary: x\ninstall:\n  method: pip\n",
    )
    with pytest.raises(LabError, match="invalid install.method"):
        load_registry(tmp_path)


def test_validation_curl_missing_source(tmp_path: Path) -> None:
    _write_agent_yaml(
        tmp_path,
        "broken",
        "id: broken\nname: Broken\nhomepage: https://x\nbinary: x\ninstall:\n  method: curl\n",
    )
    with pytest.raises(LabError, match="requires install.source"):
        load_registry(tmp_path)


def test_validation_gh_release_missing_asset(tmp_path: Path) -> None:
    _write_agent_yaml(
        tmp_path,
        "broken",
        "id: broken\nname: Broken\nhomepage: https://x\nbinary: x\n"
        "install:\n  method: gh-release\n  repo: a/b\n",
    )
    with pytest.raises(LabError, match="requires install.repo and install.asset"):
        load_registry(tmp_path)


def test_validation_bad_yaml(tmp_path: Path) -> None:
    _write_agent_yaml(tmp_path, "broken", "id: [unclosed")
    with pytest.raises(LabError, match="Invalid YAML"):
        load_registry(tmp_path)


def test_validation_config_without_path(tmp_path: Path) -> None:
    _write_agent_yaml(
        tmp_path,
        "broken",
        "id: broken\nname: Broken\nhomepage: https://x\nbinary: x\n"
        "install:\n  method: npm\n  source: x\nconfig:\n  format: json\n",
    )
    with pytest.raises(LabError, match="config requires config.path"):
        load_registry(tmp_path)


# ---------------------------------------------------------------------------
# Status detection
# ---------------------------------------------------------------------------


def test_registry_agent_status_binary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    hermes = get_registry_agent("hermes")
    assert hermes is not None
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: True)
    status = registry_agent_status(hermes, home=Path("/nonexistent-home"))
    assert status["id"] == "hermes"
    assert status["binary_ok"] is True
    assert status["installed"] is False  # config not present


def test_registry_agent_status_full(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    openclaw = get_registry_agent("openclaw")
    assert openclaw is not None
    home = tmp_path / "home"
    (home / ".openclaw").mkdir(parents=True)
    (home / ".openclaw" / "openclaw.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: True)
    status = registry_agent_status(openclaw, home=home)
    assert status["config_ok"] is True
    assert status["installed"] is True


# ---------------------------------------------------------------------------
# Verify issues (installed-only gating)
# ---------------------------------------------------------------------------


def test_verify_issues_nothing_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing on PATH → installed_only reports nothing (fresh image gate).
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: False)
    assert registry_verify_issues(home=Path("/nonexistent-home"), installed_only=True) == []


def test_verify_issues_full_reports_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: False)
    issues = registry_verify_issues(home=Path("/nonexistent-home"), installed_only=False)
    assert any("binary not found" in i and "hermes" in i for i in issues)


def test_verify_issues_installed_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: True)
    issues = registry_verify_issues(home=home, installed_only=True)
    assert any("config missing" in i and "hermes" in i for i in issues)


# ---------------------------------------------------------------------------
# Install dispatch
# ---------------------------------------------------------------------------


def test_install_registry_agent_unknown() -> None:
    with pytest.raises(LabError, match="Unknown agent"):
        install_registry_agent("not-an-agent")


def test_install_registry_agent_tools_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    # hermes/openclaw exist in install.TOOLS → keep the battle-tested installer.
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        "astroai_lab.agent.install.install_tool",
        lambda name, dry_run=False: calls.append((name, dry_run)),
    )
    install_registry_agent("hermes", dry_run=True)
    assert calls == [("hermes", True)]


def test_install_registry_agent_migrated_not_in_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrated agents no longer resolve through install.TOOLS."""
    from astroai_lab.agent import install as install_mod

    calls: list[str] = []
    monkeypatch.setattr(install_mod, "install_tool", lambda name, dry_run=False: calls.append(name))
    # kilo is registry-driven now — install_tool must NOT be called for it.
    install_registry_agent("kilo", dry_run=True)
    assert calls == []


def test_install_registry_agent_curl_env_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_install_curl expands {bin_dir} tokens in install.env (goose/kilo/opencode)."""
    from astroai_lab.agent import install as install_mod
    from astroai_lab.agent import registry as registry_mod

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    captured: dict[str, str | None] = {}

    def fake_pipe_bash(url: str, *, env: dict[str, str] | None = None) -> None:
        captured["env"] = env
        (bin_dir / "goose").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(install_mod, "_curl_pipe_bash", fake_pipe_bash)
    monkeypatch.setattr(install_mod, "_bin_dir", lambda: bin_dir)
    monkeypatch.setattr(install_mod, "_link_into_local_bin", lambda *a, **k: None)
    monkeypatch.setattr(install_mod, "_verify_cmd", lambda *a, **k: None)

    agent = {
        "id": "goose",
        "binary": "goose",
        "install": {
            "method": "curl",
            "source": "https://x/download.sh",
            "env": {"GOOSE_BIN_DIR": "{bin_dir}", "CONFIGURE": "false"},
        },
    }
    assert registry_mod._install_curl(agent) == "goose"
    assert captured["env"] == {"GOOSE_BIN_DIR": str(bin_dir), "CONFIGURE": "false"}


def test_install_gh_release_templates_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    """_install_gh_release replaces {arch} with platform.machine() (codex)."""
    from astroai_lab.agent import install as install_mod
    from astroai_lab.agent import registry as registry_mod

    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        install_mod, "_gh_release_bin", lambda repo, asset, binary: seen.append((asset, binary))
    )
    monkeypatch.setattr(install_mod, "_verify_cmd", lambda *a, **k: None)
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    agent = {
        "id": "codex",
        "binary": "codex",
        "install": {
            "method": "gh-release",
            "repo": "openai/codex",
            "asset": "codex-{arch}-unknown-linux-musl.tar.gz",
        },
    }
    assert registry_mod._install_gh_release(agent) == "codex"
    assert seen == [("codex-x86_64-unknown-linux-musl.tar.gz", "codex")]


def test_install_registry_agent_curl_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    # A registry-only agent (not in TOOLS) with method curl → curl installer.
    from astroai_lab.agent import registry as registry_mod

    monkeypatch.setattr("astroai_lab.agent.install.TOOLS", {}, raising=False)

    def fake_install_npm(agent):  # pragma: no cover
        return "never"

    monkeypatch.setattr(registry_mod, "_install_curl", lambda agent: "curl-done")
    monkeypatch.setattr(registry_mod, "_install_npm", fake_install_npm)
    monkeypatch.setattr(registry_mod, "_install_uv_tool", fake_install_npm)
    monkeypatch.setattr(registry_mod, "_install_gh_release", fake_install_npm)

    agent = {"id": "regonly", "install": {"method": "curl", "source": "https://x/i.sh"}}
    monkeypatch.setattr(registry_mod, "get_registry_agent", lambda _: agent)
    assert install_registry_agent("regonly") == "curl-done"


# ---------------------------------------------------------------------------
# Catalog + CLI integration
# ---------------------------------------------------------------------------


def test_catalog_driven_by_registry(tmp_path: Path) -> None:
    catalog = list_agent_catalog(home=tmp_path)
    by_id = {item["id"]: item for item in catalog}
    assert by_id["hermes"]["name"] == "Hermes Agent"
    assert by_id["openclaw"]["install_command"] == "astroai-lab agent install openclaw"
    assert by_id["hermes"]["kind"] == "agent"
    # Migrated agents are registry-driven too.
    assert by_id["kilo"]["name"] == "Kilo CLI"
    assert by_id["kilo"]["install_command"] == "astroai-lab agent install kilo"
    assert by_id["goose"]["kind"] == "agent"


def test_cli_agent_list_json_includes_registry() -> None:
    result = runner.invoke(app, ["--json", "agent", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "registry" in data
    ids = {row["id"] for row in data["registry"]}
    assert {"hermes", "openclaw", "kilo", "goose", "cline", "opencode", "codex"} <= ids


def test_cli_agent_install_list_includes_migrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`agent install` (no arg) surfaces registry agents as installable."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["--json", "agent", "install"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    names = {str(row["name"]) for row in data}
    assert {"kilo", "goose", "cline", "opencode", "codex"} <= names
    kilo = next(r for r in data if r["name"] == "kilo")
    assert kilo["binary"] == "kilo"


def test_cli_agent_list_human_shows_registry() -> None:
    result = runner.invoke(app, ["agent", "list"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "Registered agents" in out


def test_cli_agent_catalog_includes_registry_agents() -> None:
    result = runner.invoke(app, ["--json", "agent", "catalog"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = {item["id"] for item in data}
    assert {"hermes", "openclaw"} <= ids


def test_cli_agent_install_unknown() -> None:
    result = runner.invoke(app, ["--json", "agent", "install", "not-an-agent"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "Unknown tool" in data["errors"][0]


def test_verify_setup_includes_registry_for_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fresh home, nothing on PATH → verify_setup reports no registry issues.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("astroai_lab.agent.registry.tool_on_path", lambda _: False)
    from astroai_lab.agent.inventory import verify_setup

    issues = verify_setup(home)
    assert not any("binary not found" in i and "hermes" in i for i in issues)
    # ...but the standard cursor/config checks still fire on a fresh home.
    assert issues
