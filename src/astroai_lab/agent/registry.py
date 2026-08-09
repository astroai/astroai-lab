"""Agent registry: YAML single source of truth (docs/agent-rethink-plan.md Phase 1).

One file per agent under ``data/agent/agents/*.yaml`` drives ``agent list``,
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


_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9.]+)?)")


def probe_version(binary: str, *, timeout: float = 0.8) -> str | None:
    """Best-effort installed version from ``binary --version`` (no network).

    Returns the first semver-ish token, or None when the binary is missing /
    hangs / prints nothing parseable. ponytail: sub-second ceiling — upgrade
    path is a per-agent version command in the registry YAML.
    """
    import os
    import shutil
    import subprocess

    # Skip probes in unit tests unless explicitly enabled (avoids hung CLIs).
    if os.environ.get("ASTROAI_LAB_PROBE_VERSION", "1") in ("0", "false", "no"):
        return None

    resolved = shutil.which(binary)
    if resolved is None and not tool_on_path(binary):
        return None
    cmd = resolved or binary
    try:
        proc = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def registry_agent_status(
    agent: dict[str, Any],
    home: Path | None = None,
    *,
    probe_ver: bool = False,
) -> dict[str, Any]:
    """Installed status for a registry agent: binary on PATH + config present.

    Binary detection reuses ``install.tool_on_path`` (session bin dirs +
    npm prefix + PATH), so it matches what `agent install` actually produces.
    Version probing is opt-in (``probe_ver=True``) — some CLIs hang on
    ``--version``.
    """
    home = home or Path.home()
    binary = str(agent["binary"])
    from astroai_lab.agent.install import TOOLS

    # Prefer TOOLS key (handles remaps like qoder→qodercli) when the agent id
    # is also a TOOLS entry; otherwise probe the declared binary name.
    path_key = agent["id"] if agent["id"] in TOOLS else binary
    binary_ok = tool_on_path(path_key)
    config = agent.get("config") or {}
    cfg_path: Path | None = None
    config_declared = bool(config.get("path"))
    # No config declared → N/A (ok for health, shown as "·" in the table).
    config_ok = True
    if config_declared:
        cfg_path = _expand_home(str(config["path"]), home)
        config_ok = cfg_path.is_file()
    version = probe_version(binary) if (probe_ver and binary_ok) else None
    return {
        "id": agent["id"],
        "name": agent["name"],
        "binary": binary,
        "binary_ok": binary_ok,
        "config": str(cfg_path) if cfg_path else "",
        "config_ok": config_ok,
        "config_declared": config_declared,
        "installed": binary_ok and (config_ok if config_declared else binary_ok),
        "version": version,
        "summary": agent.get("summary", ""),
    }


def tool_on_path(name: str) -> bool:
    """Re-export of install.tool_on_path so registry callers can mock it locally."""
    from astroai_lab.agent.install import tool_on_path as _tool_on_path

    return _tool_on_path(name)


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
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent list")

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
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent list")

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
                    quiet=True,  # keep stdout clean for `--json agent remove/wipe`
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


# ---------------------------------------------------------------------------
# Registry-driven setup / update (Phase 2 `agent setup <id>` + `agent update <id>`)
# ---------------------------------------------------------------------------


def list_installed_registry_agents(home: Path | None = None) -> list[dict[str, Any]]:
    """Registry agents whose binary is currently on PATH (`agent setup --all`)."""
    home = home or Path.home()
    return [a for a in load_registry() if registry_agent_status(a, home)["binary_ok"]]


def _config_scaffold(agent: dict[str, Any]) -> str:
    """Minimal scaffold for a missing registry ``config.path``.

    JSON5/JSONC get a ``//`` comment header (JSONC/JSON5 do not support ``#``
    comments — parse_jsonc only strips ``//`` and ``/* */``); strict JSON gets
    a header-free body; YAML/TOML/markdown get ``#`` headers. All bodies parse
    to an empty mapping / empty file respectively.
    """
    fmt = str((agent.get("config") or {}).get("format", "json"))
    name = agent.get("name", agent["id"])
    header = f"# {name} — scaffolded by `astroai-lab agent setup {agent['id']}`\n"
    if fmt == "json":
        return "{}\n"
    if fmt in ("jsonc", "json5"):
        return f"// {name} — scaffolded by `astroai-lab agent setup {agent['id']}`\n{{}}\n"
    if fmt == "yaml":
        return header + "{}\n"
    # toml / markdown / unknown: comment-only body stays valid.
    return header + "\n"


def _run_post_install(command: str) -> None:
    """Run a ``setup.post_install`` shell command (interactive agents only)."""
    import subprocess

    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    try:
        proc = subprocess.run(command, shell=True, timeout=INSTALL_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        raise LabError(
            f"post_install timed out after {INSTALL_TIMEOUT_SEC}s",
            hint="Re-run with a higher ASTROAI_LAB_AGENT_INSTALL_TIMEOUT",
        ) from exc
    if proc.returncode != 0:
        raise LabError(f"post_install exited {proc.returncode}: {command}")


def setup_registry_agent(
    agent_id: str,
    *,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    post_install: bool = False,
) -> dict[str, Any]:
    """Registry-driven `agent setup <id>` (docs/agent-rethink-plan.md Phase 2).

    Writes configs/skills/MCP for ONE registered agent:

    1. Scaffold the declared config file when missing (never clobber existing).
    2. Create the agent's skills dir (AGENT_SKILL_DIRS, when declared).
    3. Re-apply every plugin whose support matrix includes this agent.
    4. Optionally run ``setup.post_install`` (interactive — opt-in).
    5. Record the setup stamp (mode=setup:<id>).

    Returns ``{ok, partial, agent, actions, errors}`` (human-readable action
    strings) for JSON output.
    """
    agent = get_registry_agent(agent_id)
    if agent is None:
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent list")
    home = home or Path.home()
    actions: list[str] = []
    errors: list[str] = []

    config = agent.get("config") or {}
    if config.get("path"):
        cfg = _expand_home(str(config["path"]), home)
        if cfg.is_file():
            actions.append(f"config exists ({cfg})")
        elif dry_run:
            actions.append(f"would create config ({cfg})")
        else:
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(_config_scaffold(agent), encoding="utf-8")
            actions.append(f"created config ({cfg})")

    from astroai_lab.agent.addons import AGENT_SKILL_DIRS

    rel = AGENT_SKILL_DIRS.get(agent_id)
    if rel:
        skills_dir = home / rel
        if skills_dir.is_dir():
            actions.append(f"skills dir present ({skills_dir})")
        elif dry_run:
            actions.append(f"would create skills dir ({skills_dir})")
        else:
            skills_dir.mkdir(parents=True, exist_ok=True)
            actions.append(f"created skills dir ({skills_dir})")

    from astroai_lab.agent import plugins as agent_plugins

    for result in agent_plugins.apply_agent_plugins(
        agent_id, home=home, force=force, dry_run=dry_run
    ):
        if result.status == "failed":
            errors.append(f"plugin {result.plugin} ({result.agent}): {result.detail}")
        elif result.status in ("installed", "would_install", "updated"):
            actions.append(
                f"plugin {result.status.replace('_', ' ')} {result.plugin} ({result.agent})"
            )

    post = (agent.get("setup") or {}).get("post_install")
    if post and post_install:
        if dry_run:
            actions.append(f"would run post-install ({post})")
        else:
            try:
                _run_post_install(str(post))
                actions.append(f"ran post-install ({post})")
            except LabError as exc:
                errors.append(f"post-install: {exc}")

    ok = not errors
    if not dry_run and ok:
        from astroai_lab.agent.setup_state import record_setup_ok

        record_setup_ok(home, mode=f"setup:{agent_id}")
    return {
        "ok": ok,
        "partial": bool(actions) and bool(errors),
        "agent": agent_id,
        "actions": actions,
        "errors": errors,
    }


def update_registry_agent(
    agent_id: str,
    *,
    home: Path | None = None,
    force_reinstall: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Registry-driven `agent update <id>` (docs/agent-rethink-plan.md Phase 2).

    1. Refresh the CLI binary (install if missing, or always with --reinstall).
    2. Force re-apply every plugin supporting this agent (skills/MCP/config).
    3. Refresh the setup stamp (mode=update:<id>).

    Returns ``{ok, partial, agent, actions, errors}`` for JSON output.
    """
    agent = get_registry_agent(agent_id)
    if agent is None:
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent list")
    home = home or Path.home()
    actions: list[str] = []
    errors: list[str] = []

    status = registry_agent_status(agent, home)
    if status["binary_ok"] and not force_reinstall:
        actions.append(f"binary up-to-date ({agent_id})")
    else:
        verb = "reinstall" if force_reinstall else "install"
        try:
            install_registry_agent(agent_id, dry_run=dry_run)
            actions.append(f"binary {verb} ({agent_id})")
        except LabError as exc:
            errors.append(f"binary {agent_id}: {exc}")

    from astroai_lab.agent import plugins as agent_plugins

    for result in agent_plugins.apply_agent_plugins(
        agent_id, home=home, force=True, dry_run=dry_run
    ):
        if result.status == "failed":
            errors.append(f"plugin {result.plugin} ({result.agent}): {result.detail}")
        elif result.status in ("installed", "would_install", "updated", "removed"):
            actions.append(
                f"plugin {result.status.replace('_', ' ')} {result.plugin} ({result.agent})"
            )

    ok = not errors
    if not dry_run and ok:
        from astroai_lab.agent.setup_state import record_setup_ok

        record_setup_ok(home, mode=f"update:{agent_id}")
    return {
        "ok": ok,
        "partial": bool(actions) and bool(errors),
        "agent": agent_id,
        "actions": actions,
        "errors": errors,
    }


def fix_registry_agent(
    agent_id: str,
    *,
    home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Registry-driven `agent repair <id>` (docs/agent-rethink-plan.md Phase 2).

    Regenerate/sanitize ONE registered agent's config from the registry,
    reusing ``fix.py``'s repair pattern (syntax check → reset to a minimal
    valid body) with the format-aware parse from ``agent_config``:

    1. Missing config → scaffold it (format-aware; JSONC/JSON5 keep a ``//``
       header, strict JSON gets ``{}\n``, YAML/TOML/markdown comment bodies).
    2. Present but unparseable → reset to the scaffold (markdown is read-only:
       no repair).
    3. Present + parseable → nothing to fix.
    4. Ensure the agent's skills dir exists (like `agent setup <id>`).
    5. Refresh the setup stamp / clear the failed marker when healthy.

    A repaired (reset) config loses plugin-written entries — run
    `agent update <id>` afterwards to force re-apply the agent's plugins.

    Returns ``{ok, partial, agent, actions, errors}`` for JSON output.
    """
    agent = get_registry_agent(agent_id)
    if agent is None:
        raise LabError(f"Unknown agent: {agent_id}", hint="astroai-lab agent list")
    home = home or Path.home()
    actions: list[str] = []
    errors: list[str] = []

    config = agent.get("config") or {}
    if config.get("path"):
        cfg = _expand_home(str(config["path"]), home)
        fmt = str(config.get("format", "json"))
        if not cfg.is_file():
            if dry_run:
                actions.append(f"would create config ({cfg})")
            else:
                cfg.parent.mkdir(parents=True, exist_ok=True)
                cfg.write_text(_config_scaffold(agent), encoding="utf-8")
                actions.append(f"created config ({cfg})")
        elif fmt == "markdown":
            actions.append(f"config healthy (markdown read-only) ({cfg})")
        else:
            from astroai_lab.agent import agent_config as agent_config_mod

            text = cfg.read_text(encoding="utf-8", errors="replace")
            try:
                agent_config_mod.validate_config_text(agent_id, text, home=home)
                actions.append(f"config healthy ({cfg})")
            except LabError:
                if dry_run:
                    actions.append(f"would repair broken {fmt} config ({cfg})")
                else:
                    cfg.parent.mkdir(parents=True, exist_ok=True)
                    cfg.write_text(_config_scaffold(agent), encoding="utf-8")
                    actions.append(f"repaired broken {fmt} config ({cfg})")
    else:
        actions.append("no config declared")

    from astroai_lab.agent.addons import AGENT_SKILL_DIRS

    rel = AGENT_SKILL_DIRS.get(agent_id)
    if rel:
        skills_dir = home / rel
        if skills_dir.is_dir():
            actions.append(f"skills dir present ({skills_dir})")
        elif dry_run:
            actions.append(f"would create skills dir ({skills_dir})")
        else:
            skills_dir.mkdir(parents=True, exist_ok=True)
            actions.append(f"created skills dir ({skills_dir})")

    ok = not errors
    if not dry_run and ok:
        from astroai_lab.agent.setup_state import record_setup_ok

        record_setup_ok(home, mode=f"repair:{agent_id}")
    return {
        "ok": ok,
        "partial": bool(actions) and bool(errors),
        "agent": agent_id,
        "actions": actions,
        "errors": errors,
    }
