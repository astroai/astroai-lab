from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from astroai_lab.agent.bundles import agent_setup, install_file, list_bundles, verify_setup
from astroai_lab.cli.main import app

runner = CliRunner()


def test_bundle_root_exists() -> None:
    from astroai_lab.agent.bundle_path import bundle_root

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


def test_agent_verify_fresh_home_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No agents installed → verify passes (no Cursor nag)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.agent.install.classify_binary",
        lambda *a, **k: {
            "binary": "x",
            "path": None,
            "source": "missing",
            "managed": False,
            "home_install": False,
            "home_path": None,
        },
    )
    issues = verify_setup(home)
    assert issues == []


def test_agent_verify_cursor_required_when_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    def _classify(binary: str, *, home=None):
        # Cursor Agent upstream binary is still named `agent`.
        if binary in ("agent", "cursor"):
            return {
                "binary": binary,
                "path": "/tmp/agent",
                "source": "managed",
                "managed": True,
                "home_install": False,
                "home_path": None,
            }
        return {
            "binary": binary,
            "path": None,
            "source": "missing",
            "managed": False,
            "home_install": False,
            "home_path": None,
        }

    monkeypatch.setattr("astroai_lab.agent.install.classify_binary", _classify)
    issues = verify_setup(home)
    assert any("Cursor MCP not configured" in i for i in issues)


def test_agent_verify_opencode_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.agent.bundles import verify_config_syntax

    home = tmp_path / "home"
    oc = home / ".config" / "opencode"
    oc.mkdir(parents=True)
    (oc / "opencode.json").write_text("{ mcp: { broken } }\n")  # invalid JSON
    monkeypatch.setenv("HOME", str(home))
    issues = verify_config_syntax(home)
    assert any("syntax error" in i and "opencode" in i for i in issues)


def test_agent_verify_jsonc_ok(tmp_path: Path) -> None:
    from astroai_lab.agent.bundles import verify_config_syntax

    home = tmp_path / "home"
    oc = home / ".config" / "opencode"
    oc.mkdir(parents=True)
    (oc / "opencode.json").write_text(
        '{\n  // comment\n  "mcp": { "a": {} },\n}\n',
        encoding="utf-8",
    )
    assert verify_config_syntax(home) == []


def test_agent_install_list() -> None:
    result = runner.invoke(app, ["agent", "install"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "kilo" in out
    assert "zcode" in out or "omp" in out


def test_agent_list_overview() -> None:
    result = runner.invoke(app, ["agent", "list"])
    assert result.exit_code in (0, 1)
    out = result.stdout + result.stderr
    assert "Bin" in out and "Cfg" in out
    assert "list config" in out.lower() or "agent install kilo" in out
    cfg = runner.invoke(app, ["agent", "list", "config"])
    assert cfg.exit_code == 0
    bout = cfg.stdout + cfg.stderr
    assert "ponytail" in bout or "Configs" in bout


def test_agent_setup_list() -> None:
    result = runner.invoke(app, ["agent", "setup", "--list"])
    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "cursor" in out


def test_agent_setup_cli_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--dry-run", "agent", "setup", "cli"])
    assert result.exit_code == 0


def test_install_tool_unknown() -> None:
    from astroai_lab.agent.install import install_tool
    from astroai_lab.errors import LabError

    with pytest.raises(LabError, match="Unknown tool"):
        install_tool("not-a-tool")


def test_install_tool_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.agent.install import install_tool

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("astroai_lab.agent.install.refuse_if_home_owned", lambda *a, **k: None)
    install_tool("node", dry_run=True)


def test_merge_mcp_servers(tmp_path: Path) -> None:
    from astroai_lab.agent.bundles import merge_mcp_servers
    from astroai_lab.utils.json_utils import read_json, write_json

    src = tmp_path / "src.json"
    dst = tmp_path / "dst.json"
    src.write_text('{"mcpServers": {"a": {"url": "x"}}, "keepMe": false}')
    write_json(dst, {"mcpServers": {"b": {"url": "y"}}, "userKey": 1})
    merge_mcp_servers(src, dst, force=True, dry_run=False)
    data = read_json(dst)
    assert data["userKey"] == 1  # never clobber whole file
    assert data["mcpServers"]["a"]["url"] == "x"
    assert data["mcpServers"]["b"]["url"] == "y"


def test_npm_global_install_cmd_adds_allow_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astroai_lab.agent import install as install_mod

    monkeypatch.setattr(install_mod, "_npm_version_tuple", lambda: (11, 17))
    cmd = install_mod.npm_global_install_cmd(
        tmp_path / "prefix", "@oh-my-pi/pi-coding-agent@latest"
    )
    assert cmd[:4] == ["npm", "install", "-g", "--prefix"]
    assert "--dangerously-allow-all-scripts" in cmd
    assert cmd[-1] == "@oh-my-pi/pi-coding-agent@latest"


def test_npm_global_install_cmd_skips_flag_on_old_npm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astroai_lab.agent import install as install_mod

    monkeypatch.setattr(install_mod, "_npm_version_tuple", lambda: (10, 9))
    cmd = install_mod.npm_global_install_cmd(tmp_path / "prefix", "left-pad@1.3.0")
    assert "--dangerously-allow-all-scripts" not in cmd


def test_npm_install_environ_silences_update_notifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astroai_lab.agent import install as install_mod

    monkeypatch.setattr(
        install_mod,
        "_session_environ",
        lambda extra=None: {"PATH": "/usr/bin", **(extra or {})},
    )
    env = install_mod.npm_install_environ()
    assert env["NPM_CONFIG_UPDATE_NOTIFIER"] == "false"
    assert env["NPM_CONFIG_DANGEROUSLY_ALLOW_ALL_SCRIPTS"] == "true"


def test_cursor_tool_and_binary() -> None:
    from astroai_lab.agent import install as install_mod

    assert install_mod.tool_binary("cursor") == "agent"
    assert "cursor" in install_mod.TOOLS
    assert "agent" not in install_mod.TOOLS


def test_cli_install_agent_name_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy name `agent` is not accepted; use `cursor`."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["--json", "--dry-run", "agent", "install", "agent"])
    assert result.exit_code == 1
    import json

    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "Unknown" in data["errors"][0]


def test_classify_binary_managed_vs_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.agent import install as install_mod

    home = tmp_path / "home"
    scratch_bin = tmp_path / "scratch" / "bin"
    home.mkdir()
    scratch_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(install_mod, "_bin_dir", lambda: scratch_bin)
    monkeypatch.setattr(install_mod, "_npm_prefix", lambda: scratch_bin.parent)
    monkeypatch.setattr(
        install_mod,
        "resolve_session_env",
        lambda ensure=False: type(
            "E",
            (),
            {
                "astroai_lab_bin_dir": scratch_bin,
                "astroai_lab_npm_prefix": scratch_bin.parent,
            },
        )(),
    )

    managed = scratch_bin / "kilo"
    managed.write_text("#!/bin/sh\n", encoding="utf-8")
    managed.chmod(0o755)
    info = install_mod.classify_binary("kilo", home=home)
    assert info["source"] == install_mod.BINARY_SOURCE_MANAGED
    assert info["managed"] is True

    home_bin = home / ".local" / "bin"
    home_bin.mkdir(parents=True)
    (home_bin / "goose").write_text("#!/bin/sh\n", encoding="utf-8")
    info_home = install_mod.classify_binary("goose", home=home)
    assert info_home["source"] == install_mod.BINARY_SOURCE_HOME
    assert info_home["home_install"] is True
    assert info_home["managed"] is False

    with pytest.raises(Exception, match="already installed under your home"):
        install_mod.refuse_if_home_owned("goose", home=home)


def test_remove_home_owned_requires_clean_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from astroai_lab.agent import install as install_mod
    from astroai_lab.errors import LabError

    home = tmp_path / "home"
    scratch_bin = tmp_path / "scratch" / "bin"
    home.mkdir()
    scratch_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(install_mod, "_bin_dir", lambda: scratch_bin)
    monkeypatch.setattr(install_mod, "_npm_prefix", lambda: scratch_bin.parent)
    monkeypatch.setattr(install_mod.shutil, "which", lambda _: None)
    session = SimpleNamespace(
        astroai_lab_bin_dir=scratch_bin,
        astroai_lab_npm_prefix=scratch_bin.parent,
    )
    session.exports = dict
    monkeypatch.setattr(install_mod, "resolve_session_env", lambda ensure=False: session)
    home_bin = home / ".local" / "bin"
    home_bin.mkdir(parents=True)
    (home_bin / "copilot").write_text("#!/bin/sh\n", encoding="utf-8")

    with pytest.raises(LabError, match="--clean-home"):
        install_mod.uninstall_tool("copilot", home=home, dry_run=True)

    results = install_mod.uninstall_tool("copilot", home=home, clean_home=True, dry_run=False)
    assert not (home_bin / "copilot").exists()
    assert any(r.target.startswith("home-binary:") for r in results)
