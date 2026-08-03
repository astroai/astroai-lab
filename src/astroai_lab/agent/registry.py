"""Agent registry: YAML single source of truth (docs/agent-rethink-plan.md Phase 1).

One file per agent under ``data/agent/agents/*.yaml`` drives ``agent catalog``,
``agent list``, ``agent install``, and ``agent verify`` for registered agents.
The schema is validated on load so a bad entry fails loudly instead of silently
degrading the CLI.

Schema (see docs/agent-rethink-plan.md §4 Phase 1):

    id: openclaw
    name: OpenClaw
    homepage: https://github.com/openclaw/openclaw
    binary: openclaw
    install:
      method: npm            # npm | curl | gh-release | uv-tool
      source: openclaw@latest
      requires_node: ">=24.15"
    config:
      path: ~/.openclaw/openclaw.json
      format: json5
      provider_key: OPENROUTER_API_KEY
    setup:
      post_install: openclaw onboard
    verify:
      - "openclaw --version"
      - "test -f ~/.openclaw/openclaw.json"
    plugins: [skill, mcp, config, addon]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.errors import LabError

INSTALL_METHODS = ("npm", "curl", "gh-release", "uv-tool")
REQUIRED_KEYS = ("id", "name", "homepage", "binary", "install")


def _agents_dir(root: Path | None = None) -> Path:
    return (root or bundle_root()) / "agents"


def _expand_home(path: str, home: Path) -> Path:
    """Expand a leading `~` against an explicit home (test-friendly)."""
    if path == "~":
        return home
    if path.startswith("~/"):
        return home / path[2:]
    return Path(path).expanduser()


def _validate(data: dict[str, Any], source: Path) -> dict[str, Any]:
    """Validate + normalize a single registry entry; raise LabError on problems."""
    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        raise LabError(
            f"Agent registry entry {source.name} missing required key(s): {', '.join(missing)}"
        )
    install = data.get("install") or {}
    method = install.get("method")
    if method not in INSTALL_METHODS:
        raise LabError(
            f"Agent {data['id']} has invalid install.method={method!r} "
            f"(expected one of {', '.join(INSTALL_METHODS)}) in {source.name}"
        )
    if method in ("npm", "curl", "uv-tool") and not install.get("source"):
        raise LabError(
            f"Agent {data['id']} install.method={method} requires install.source in {source.name}"
        )
    if method == "gh-release" and not (install.get("repo") and install.get("asset")):
        raise LabError(
            f"Agent {data['id']} install.method=gh-release requires "
            f"install.repo and install.asset in {source.name}"
        )
    if data.get("config") and not data["config"].get("path"):
        raise LabError(f"Agent {data['id']} config requires config.path in {source.name}")
    return data


def load_registry(root: Path | None = None) -> list[dict[str, Any]]:
    """Load + validate every ``agents/*.yaml`` entry, sorted by id."""
    d = _agents_dir(root)
    if not d.is_dir():
        return []
    agents: list[dict[str, Any]] = []
    for path in sorted(d.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise LabError(f"Invalid YAML in agent registry {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise LabError(f"Agent registry entry must be a mapping: {path}")
        agents.append(_validate(raw, path))
    return agents


def list_registry_agents(root: Path | None = None) -> list[dict[str, Any]]:
    return load_registry(root)


def get_registry_agent(agent_id: str, root: Path | None = None) -> dict[str, Any] | None:
    for agent in load_registry(root):
        if agent["id"] == agent_id:
            return agent
    return None


def registry_ids(root: Path | None = None) -> set[str]:
    return {a["id"] for a in load_registry(root)}


def registry_agent_status(
    agent: dict[str, Any],
    home: Path | None = None,
) -> dict[str, Any]:
    """Installed status for a registry agent: binary on PATH + config present.

    Binary detection reuses ``install.tool_on_path`` (session bin dirs +
    npm prefix + PATH), so it matches what `agent install` actually produces.
    """
    home = home or Path.home()
    binary = str(agent["binary"])
    binary_ok = tool_on_path(binary)
    config = agent.get("config") or {}
    cfg_path: Path | None = None
    # No config declared → nothing to check, so config is OK by default.
    config_ok = not bool(config.get("path"))
    if config.get("path"):
        cfg_path = _expand_home(str(config["path"]), home)
        config_ok = cfg_path.is_file()
    return {
        "id": agent["id"],
        "name": agent["name"],
        "binary": binary,
        "binary_ok": binary_ok,
        "config": str(cfg_path) if cfg_path else "",
        "config_ok": config_ok,
        "installed": binary_ok and config_ok,
    }


def registry_verify_issues(
    home: Path | None = None,
    *,
    root: Path | None = None,
    installed_only: bool = False,
) -> list[str]:
    """Config-verify issues for every registered agent (binary + config checks).

    With ``installed_only=True``, agents whose binary is not on PATH are
    skipped (no issue). `agent verify` uses this so fresh images that don't
    ship hermes/openclaw still pass the container gate; agents that ARE
    installed still get their config checked.
    """
    home = home or Path.home()
    issues: list[str] = []
    for agent in load_registry(root):
        status = registry_agent_status(agent, home)
        if not status["binary_ok"]:
            if installed_only:
                continue
            issues.append(
                f"{agent['name']} binary not found ({status['binary']}) — run: "
                f"astroai-lab agent install {agent['id']}"
            )
            continue
        if agent.get("config", {}).get("path") and not status["config_ok"]:
            issues.append(f"{agent['name']} config missing ({status['config']})")
    return issues


def _install_npm(agent: dict[str, Any]) -> str:
    from astroai_lab.agent.install import (
        _link_into_local_bin,
        _npm_prefix,
        _require,
        _session_environ,
        _verify_cmd,
        run,
    )
    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    binary = agent["binary"]
    _require("npm")
    run(
        ["npm", "install", "-g", "--prefix", str(_npm_prefix()), str(agent["install"]["source"])],
        env=_session_environ(),
        timeout=INSTALL_TIMEOUT_SEC,
    )
    bin_path = _npm_prefix() / "bin" / binary
    _link_into_local_bin(bin_path, binary)
    _verify_cmd(binary, extra_paths=[bin_path])
    return binary


def _install_curl(agent: dict[str, Any]) -> str:
    from astroai_lab.agent.install import (
        _bin_dir,
        _curl_pipe_bash,
        _link_into_local_bin,
        _verify_cmd,
    )

    binary = agent["binary"]
    # Registry installs can pass installer-specific env (e.g. XDG_BIN_DIR,
    # GOOSE_BIN_DIR) with a {bin_dir} token expanded to the session bin dir.
    env = {
        k: str(v).replace("{bin_dir}", str(_bin_dir()))
        for k, v in (agent["install"].get("env") or {}).items()
    }
    _curl_pipe_bash(str(agent["install"]["source"]), env=env or None)
    home = Path.home()
    candidates = [
        _bin_dir() / binary,
        *(Path(p).expanduser() for p in agent["install"].get("post_binary_paths", [])),
    ]
    # self-contained installers may drop the binary in $HOME-relative spots
    candidates.extend([home / ".local" / "bin" / binary, home / f".{binary}" / "bin" / binary])
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        raise LabError(
            f"{binary} not found after install — open a new shell",
            hint="Check the installer output; binary should land in the session bin dir "
            "(see `astroai-lab env export` / ASTROAI_LAB_BIN_DIR)",
        )
    _link_into_local_bin(found, binary)
    _verify_cmd(binary, extra_paths=candidates)
    return binary


def _install_uv_tool(agent: dict[str, Any]) -> str:
    from astroai_lab.agent.install import _require, _session_environ, _verify_cmd, run
    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    binary = agent["binary"]
    _require("uv")
    run(
        ["uv", "tool", "install", "--force", str(agent["install"]["source"])],
        env=_session_environ(),
        timeout=INSTALL_TIMEOUT_SEC,
    )
    _verify_cmd(binary)
    return binary


def _install_gh_release(agent: dict[str, Any]) -> str:
    import platform

    from astroai_lab.agent.install import _gh_release_bin, _verify_cmd

    binary = agent["binary"]
    install = agent["install"]
    # {arch} templates to platform.machine() (x86_64/aarch64) for per-arch assets.
    asset = str(install["asset"]).replace("{arch}", platform.machine())
    _gh_release_bin(str(install["repo"]), asset, binary)
    _verify_cmd(binary)
    return binary


def install_registry_agent(agent_id: str, *, dry_run: bool = False) -> str:
    """Install a registered agent by id, dispatching on install.method.

    Registered agents that already exist in ``install.TOOLS`` (hermes, openclaw)
    keep their battle-tested installer via ``install_tool``; future registry-only
    agents dispatch by method here.
    """
    agent = get_registry_agent(agent_id)
    if agent is None:
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent catalog")

    from astroai_lab.agent.install import TOOLS, install_tool

    if agent_id in TOOLS:
        install_tool(agent_id, dry_run=dry_run)
        return agent_id
    if dry_run:
        return agent_id

    method = agent["install"]["method"]
    if method == "npm":
        return _install_npm(agent)
    if method == "curl":
        return _install_curl(agent)
    if method == "uv-tool":
        return _install_uv_tool(agent)
    if method == "gh-release":
        return _install_gh_release(agent)
    raise LabError(f"Agent {agent_id} has unsupported install.method={method!r}")


def tool_on_path(name: str) -> bool:
    """Re-export of install.tool_on_path so registry callers can mock it locally."""
    from astroai_lab.agent.install import tool_on_path as _tool_on_path

    return _tool_on_path(name)


def remove_registry_agent(
    agent_id: str,
    *,
    home: Path | None = None,
    purge: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Uninstall a registered agent by id (Phase 2 `agent remove`).

    Agents that exist in ``install.TOOLS`` (hermes, openclaw) keep their
    battle-tested uninstaller via ``install.uninstall_tool``; registry-only
    agents are removed by install method here. Returns result dicts for JSON.
    """
    agent = get_registry_agent(agent_id)
    if agent is None:
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent catalog")

    from astroai_lab.agent.install import TOOLS, uninstall_tool

    if agent_id in TOOLS:
        results = uninstall_tool(agent_id, home=home, purge=purge, dry_run=dry_run)
        return [r.__dict__ for r in results]
    return _remove_registry_method(agent, home=home, purge=purge, dry_run=dry_run)


def _remove_registry_method(
    agent: dict[str, Any],
    *,
    home: Path | None,
    purge: bool,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Method-based removal for registry agents not present in install.TOOLS."""
    import contextlib
    import shutil
    import subprocess

    from astroai_lab.agent.install import (
        RemoveResult,
        _bin_dir,
        _npm_prefix,
        _session_environ,
    )
    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    home = home or Path.home()
    agent_id = agent["id"]
    binary = str(agent["binary"])
    method = agent["install"]["method"]
    results: list[dict[str, Any]] = []

    def rm(path: Path, target: str) -> None:
        if not (path.exists() or path.is_symlink()):
            return
        if dry_run:
            results.append(RemoveResult(target, "would_remove", str(path)).__dict__)
        else:
            try:
                path.unlink(missing_ok=True)
                results.append(RemoveResult(target, "removed", str(path)).__dict__)
            except OSError as exc:
                results.append(RemoveResult(target, "error", str(exc)).__dict__)

    def rm_tree(path: Path, target: str) -> None:
        if not path.exists():
            return
        if dry_run:
            results.append(RemoveResult(target, "would_remove", str(path)).__dict__)
        else:
            try:
                shutil.rmtree(path)
                results.append(RemoveResult(target, "removed", str(path)).__dict__)
            except OSError as exc:
                results.append(RemoveResult(target, "error", str(exc)).__dict__)

    # npm-installed: best-effort `npm uninstall -g`, then drop bin links.
    if method == "npm":
        pkg = re.sub(r"@[^@]*$", "", str(agent["install"].get("source", binary)))
        if not dry_run and shutil.which("npm"):
            from astroai_lab.agent.install import run

            with contextlib.suppress(LabError, subprocess.CalledProcessError, OSError):
                run(
                    ["npm", "uninstall", "-g", "--prefix", str(_npm_prefix()), pkg],
                    env=_session_environ(),
                    timeout=INSTALL_TIMEOUT_SEC,
                )
        rm(_npm_prefix() / "bin" / binary, f"binary:{binary}")

    # curl / gh-release / uv-tool installers drop a self-contained binary.
    rm(_bin_dir() / binary, f"binary:{binary}")

    # Config file (registry config.path).
    config = agent.get("config") or {}
    if config.get("path"):
        cfg = _expand_home(str(config["path"]), home)
        rm(cfg, f"config:{cfg}")
        if purge and cfg.parent != home:
            rm_tree(cfg.parent, f"purge:{cfg.parent}")

    # Plugin-applied files (Phase 3 recursive removal). Run the precise
    # plugin sweep first so installed plugins report `removed` (not `skipped`),
    # then a broad sweep of ~/.<id>/skills catches any non-plugin skills.
    from astroai_lab.agent import plugins as agent_plugins

    for row in agent_plugins.remove_agent_plugin_files(agent_id, home=home, dry_run=dry_run):
        results.append(row)
    rm_tree(home / f".{agent_id}" / "skills", f"plugins:{agent_id}")

    # Setup state stamps.
    from astroai_lab.agent.setup_state import failed_path, stamp_path

    rm(stamp_path(home), "state:stamp")
    rm(failed_path(home), "state:failed")

    return results
