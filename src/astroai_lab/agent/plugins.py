"""Plugin registry: skills / MCP / config / addon packages across agents (Phase 3).

One YAML file per plugin under ``data/agent/plugins/*.yaml`` declares the
support matrix (which agents can host it) and how it is applied. ``agent
plugins install/update/remove/configure`` drive every kind; ``install``
applies to every *installed* agent in the matrix by default and ``--agent``
scopes it.

Schema (see docs/agent-rethink-plan.md §4 Phase 3):

    id: canfar-ray
    kind: skill                 # skill | mcp | config | addon
    tags: [science, ray, canfar]
    summary: Drive CANFAR Ray clusters (ensure/status/scale/dashboard)
    agents: [hermes, openclaw]  # support matrix
    install:
      source: canfar-ray        # skill: bundled dir under bundle_root()/skills/<source>
      targets:                  # optional home-relative paths (default AGENT_SKILL_DIRS)
        hermes: .hermes/skills/canfar-ray
        openclaw: .openclaw/skills/canfar-ray

Kinds:
  skill  — copy a bundled SKILL.md tree into each target agent's skill dir
  bundle — legacy github-bundle addon transport (skills + rules from a repo)
  mcp    — merge an ``mcpServers`` entry into each agent's config (configure)
  tool   — legacy cli-tool addon transport (install a CLI binary)
  rule   — legacy bundled/github-rule addon transport (Cursor rules)
  config — write a config snippet to a home-relative target path
  addon  — legacy delegation (addons.add_addon)

Any plugin whose ``install`` block declares ``type`` (bundled / github-skill /
github-bundle / github-rule / mcp-snippet / cli-tool / agent-skill) is a
legacy addon migrated from addons.json: it routes through the shared
``addons._apply_addon`` dispatcher so `agent plugins install` and
`agent add` behave identically. Entries also carry ``addon: true`` so the
`agent addons` / `agent add` surface sees them (see ``addons.load_addons``).

Removal is recursive: dropping an agent removes its plugin-applied files
(see ``remove_agent_plugin_files``, wired into ``registry._remove_registry_method``).
Dynamic URLs only — an mcp ``entry`` must reference env vars (e.g.
``$ASTROAI_RAY_JOBS_ADDRESS``), never a hardcoded per-session manager URL.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.errors import LabError
from astroai_lab.utils.json_utils import read_jsonc, write_json

PLUGIN_KINDS = ("skill", "bundle", "mcp", "tool", "rule", "config", "addon")
REQUIRED_KEYS = ("id", "kind", "summary", "agents", "install")

# Legacy addon transports (migrated from addons.json) — dispatched through
# addons._apply_addon / addons.addon_installed via plugin_as_addon.
ADDON_TRANSPORTS = (
    "bundled",
    "github-skill",
    "github-bundle",
    "github-rule",
    "mcp-snippet",
    "cli-tool",
    "agent-skill",
)

# Pseudo-agent: the global Cursor workspace. Addon transports install into
# ~/.cursor (skills/rules/mcp.json) regardless of any specific agent CLI, so
# `cursor` counts as always installed for installed_only filtering.
CURSOR_AGENT = "cursor"

# JSON/JSON5 config files that host an `mcpServers` dict (mcp kind).
_MCP_JSON_FILES = {
    "cursor": ".cursor/mcp.json",
    "copilot": ".copilot/mcp-config.json",
    "claude": ".claude.json",
}
_OPENCODE_MCP_FILE = ".config/opencode/opencode.json"  # uses `mcp` key, opencode shape
_OPENCLAW_MCP_FILE = ".openclaw/openclaw.json"  # JSON5 mcpServers
_HERMES_MCP_FILE = ".hermes/config.yaml"  # YAML mcpServers


@dataclass(frozen=True)
class PluginResult:
    plugin: str
    agent: str
    status: str  # installed | removed | skipped | would_install | would_remove | failed | no-op
    detail: str = ""


def _plugins_dir(root: Path | None = None) -> Path:
    return (root or bundle_root()) / "plugins"


def _validate(data: dict[str, Any], source: Path) -> dict[str, Any]:
    """Validate + normalize a single plugin entry; raise LabError on problems."""
    # Presence check uses `is None` so an empty list (agents: []) or empty
    # mapping (install: {}) reaches the kind-specific validation below with a
    # precise message instead of a generic "missing key" error.
    missing = [k for k in REQUIRED_KEYS if data.get(k) is None]
    if missing:
        raise LabError(
            f"Plugin registry entry {source.name} missing required key(s): {', '.join(missing)}"
        )
    kind = data["kind"]
    if kind not in PLUGIN_KINDS:
        raise LabError(
            f"Plugin {data['id']} has invalid kind={kind!r} "
            f"(expected one of {', '.join(PLUGIN_KINDS)}) in {source.name}"
        )
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        raise LabError(f"Plugin {data['id']} requires a non-empty agents support matrix")
    install = data.get("install") or {}
    if not isinstance(install, dict):
        raise LabError(f"Plugin {data['id']} install must be a mapping in {source.name}")
    transport = install.get("type")
    if transport:
        return _validate_transport(data, install, transport, source)
    if kind == "skill" and not install.get("source"):
        raise LabError(f"Plugin {data['id']} kind=skill requires install.source in {source.name}")
    if kind == "mcp" and not (install.get("server") and install.get("entry")):
        raise LabError(
            f"Plugin {data['id']} kind=mcp requires install.server and install.entry "
            f"in {source.name}"
        )
    if kind == "config" and not install.get("target"):
        raise LabError(f"Plugin {data['id']} kind=config requires install.target in {source.name}")
    if kind == "addon" and not install.get("addon"):
        raise LabError(f"Plugin {data['id']} kind=addon requires install.addon in {source.name}")
    if kind in ("bundle", "tool", "rule"):
        raise LabError(f"Plugin {data['id']} kind={kind} requires install.type in {source.name}")
    return data


def _validate_transport(
    data: dict[str, Any], install: dict[str, Any], transport: str, source: Path
) -> dict[str, Any]:
    """Validate a legacy addon transport block (migrated from addons.json)."""
    if transport not in ADDON_TRANSPORTS:
        raise LabError(
            f"Plugin {data['id']} has invalid install.type={transport!r} "
            f"(expected one of {', '.join(ADDON_TRANSPORTS)}) in {source.name}"
        )
    if transport == "github-skill" and not (install.get("repo") and install.get("path")):
        raise LabError(
            f"Plugin {data['id']} install.type=github-skill requires repo and path in {source.name}"
        )
    if transport == "github-bundle" and not (
        install.get("repo") and (install.get("skills") or install.get("rules"))
    ):
        raise LabError(
            f"Plugin {data['id']} install.type=github-bundle requires repo + "
            f"skills/rules in {source.name}"
        )
    if transport == "github-rule" and not (install.get("repo") and install.get("path")):
        raise LabError(
            f"Plugin {data['id']} install.type=github-rule requires repo and path in {source.name}"
        )
    if transport == "mcp-snippet" and not install.get("server"):
        raise LabError(
            f"Plugin {data['id']} install.type=mcp-snippet requires server in {source.name}"
        )
    if transport == "cli-tool" and not install.get("tool"):
        raise LabError(f"Plugin {data['id']} install.type=cli-tool requires tool in {source.name}")
    if transport == "agent-skill" and not install.get("agents"):
        raise LabError(
            f"Plugin {data['id']} install.type=agent-skill requires agents in {source.name}"
        )
    return data


def load_plugins(root: Path | None = None) -> list[dict[str, Any]]:
    """Load + validate every ``plugins/*.yaml`` entry, sorted by id."""
    d = _plugins_dir(root)
    if not d.is_dir():
        return []
    plugins: list[dict[str, Any]] = []
    for path in d.glob("*.yaml"):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise LabError(f"Invalid YAML in plugin registry {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise LabError(f"Plugin registry entry must be a mapping: {path}")
        plugins.append(_validate(raw, path))
    # Sort by parsed id, not by path: `ast-grep-cli.yaml` sorts before
    # `ast-grep.yaml` on disk ("-" < "."), but `ast-grep` < `ast-grep-cli`
    # as ids — the CLI surfaces ids, so sort on those.
    plugins.sort(key=lambda p: p["id"])
    return plugins


def get_plugin(plugin_id: str, root: Path | None = None) -> dict[str, Any] | None:
    for plugin in load_plugins(root):
        if plugin["id"] == plugin_id:
            return plugin
    return None


def plugin_ids(root: Path | None = None) -> set[str]:
    return {p["id"] for p in load_plugins(root)}


def _expand_home(path: str, home: Path) -> Path:
    """Resolve a target path against ``home``: `~`, `~/...`, or a bare relative
    path are all home-relative; absolute paths pass through."""
    if path == "~":
        return home
    if path.startswith("~/"):
        return home / path[2:]
    p = Path(path)
    if p.is_absolute():
        return p
    return home / p


def _skill_targets(plugin: dict[str, Any], home: Path) -> dict[str, Path]:
    """Map each support-matrix agent to its skill target dir for this plugin."""
    from astroai_lab.agent.addons import AGENT_SKILL_DIRS

    install = plugin.get("install") or {}
    explicit = install.get("targets") or {}
    out: dict[str, Path] = {}
    for agent in plugin.get("agents", []):
        if agent in explicit:
            out[agent] = _expand_home(str(explicit[agent]), home)
        elif agent in AGENT_SKILL_DIRS:
            out[agent] = home / AGENT_SKILL_DIRS[agent] / plugin["id"]
    return out


# ---------------------------------------------------------------------------
# Installed status
# ---------------------------------------------------------------------------


def _mcp_present(agent: str, server: str, home: Path) -> bool:
    """True when an mcp server entry is already merged into that agent's config."""
    if agent == "opencode":
        path = home / _OPENCODE_MCP_FILE
        if not path.is_file():
            return False
        try:
            data = read_jsonc(path)
        except Exception:  # noqa: BLE001 — presence check must not crash
            return False
        return isinstance(data, dict) and server in (data.get("mcp") or {})
    if agent == "openclaw":
        path = home / _OPENCLAW_MCP_FILE
        if not path.is_file():
            return False
        try:
            data = read_jsonc(path)
        except Exception:  # noqa: BLE001
            return False
        return isinstance(data, dict) and server in (data.get("mcpServers") or {})
    if agent == "hermes":
        path = home / _HERMES_MCP_FILE
        if not path.is_file():
            return False
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return False
        return isinstance(data, dict) and server in (data.get("mcpServers") or {})
    rel = _MCP_JSON_FILES.get(agent)
    if not rel:
        return False
    path = home / rel
    if not path.is_file():
        return False
    try:
        data = read_jsonc(path)
    except Exception:  # noqa: BLE001
        return False
    return isinstance(data, dict) and server in (data.get("mcpServers") or {})


def _agent_installed(agent_id: str, home: Path | None = None) -> bool:
    """Is this agent's CLI installed? Registry agents use binary_ok; the rest PATH."""
    from astroai_lab.agent.install import tool_on_path
    from astroai_lab.agent.registry import get_registry_agent, registry_agent_status

    if agent_id == CURSOR_AGENT:
        return True
    home = home or Path.home()
    agent = get_registry_agent(agent_id)
    if agent is not None:
        return registry_agent_status(agent, home)["binary_ok"]
    return tool_on_path(agent_id)


def plugin_installed(plugin: dict[str, Any], home: Path, agent: str | None = None) -> bool:
    """Installed status for one agent (or any agent when ``agent`` is None)."""
    kind = plugin["kind"]
    install = plugin.get("install") or {}
    agents = plugin.get("agents", [])
    if install.get("type"):
        # Legacy addon transport — delegate to the addons presence checks.
        from astroai_lab.agent.addons import addon_installed, plugin_as_addon

        return addon_installed(plugin_as_addon(plugin), home)
    if kind == "skill":
        targets = _skill_targets(plugin, home)
        if agent:
            t = targets.get(agent)
            return bool(t and (t / "SKILL.md").is_file())
        return any((t / "SKILL.md").is_file() for t in targets.values())
    if kind == "mcp":
        server = install["server"]
        if agent:
            return _mcp_present(agent, server, home)
        return any(_mcp_present(a, server, home) for a in agents)
    if kind == "config":
        target = _expand_home(str(install["target"]), home)
        return target.is_file()
    if kind == "addon":
        from astroai_lab.agent.addons import addon_installed, get_addon

        item = get_addon(str(install["addon"]))
        return bool(item and addon_installed(item, home))
    return False


def plugin_status(plugin: dict[str, Any], home: Path) -> dict[str, Any]:
    """Status row for ``agent plugins list``."""
    by_agent = {agent: plugin_installed(plugin, home, agent) for agent in plugin.get("agents", [])}
    return {
        "id": plugin["id"],
        "kind": plugin["kind"],
        "tags": plugin.get("tags", []),
        "summary": plugin.get("summary", ""),
        "homepage": plugin.get("homepage", ""),
        "default": bool(plugin.get("default")),
        "agents": plugin.get("agents", []),
        "installed": by_agent,
        "any_installed": any(by_agent.values()),
    }


def list_plugins(
    *,
    kind: str | None = None,
    agent: str | None = None,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    home = home or Path.home()
    rows: list[dict[str, Any]] = []
    for plugin in load_plugins():
        if kind and plugin["kind"] != kind:
            continue
        status = plugin_status(plugin, home)
        if agent and not status["installed"].get(agent):
            continue
        rows.append(status)
    return rows


# ---------------------------------------------------------------------------
# Install / update / remove / configure
# ---------------------------------------------------------------------------


def _selected_agents(plugin: dict[str, Any], agent: str | None) -> list[str]:
    """Support-matrix agents to apply to: --agent scopes, else every agent.

    Caller is responsible for the "only installed agents" default (install);
    remove/configure act on the full matrix (or the scoped --agent).
    """
    matrix = list(plugin.get("agents", []))
    if agent:
        if agent not in matrix:
            raise LabError(
                f"Plugin {plugin['id']} does not support agent {agent!r}",
                hint="supported: " + ", ".join(matrix),
            )
        return [agent]
    return matrix


def _install_skill(
    plugin: dict[str, Any], agent: str, home: Path, *, force: bool, dry_run: bool
) -> PluginResult:
    src = bundle_root() / "skills" / str(plugin["install"]["source"])
    if not (src / "SKILL.md").is_file():
        return PluginResult(plugin["id"], agent, "failed", f"missing bundled SKILL.md at {src}")
    targets = _skill_targets(plugin, home)
    dst = targets.get(agent)
    if dst is None:
        return PluginResult(plugin["id"], agent, "skipped", "no skill target for this agent")
    if (dst / "SKILL.md").is_file() and not force:
        return PluginResult(plugin["id"], agent, "skipped", f"already installed ({dst})")
    if dry_run:
        return PluginResult(plugin["id"], agent, "would_install", str(dst))
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return PluginResult(plugin["id"], agent, "installed", str(dst))


def _merge_mcp_entry(path: Path, server: str, entry: dict[str, Any], *, force: bool) -> bool:
    """Merge an mcpServers entry; True when merged (not just skipped).

    An unreadable (syntax-broken) config raises instead of being silently
    overwritten — mirror the addons merge helpers so user configs are never
    clobbered."""
    if path.is_file():
        try:
            data = read_jsonc(path)
        except (OSError, ValueError) as exc:
            raise LabError(
                f"Cannot merge MCP into unreadable config: {path}",
                hint=f"Fix JSON syntax first (`astroai-lab agent verify`): {exc}",
            ) from exc
        if not isinstance(data, dict):
            data = {}
    else:
        data = {}
    servers = dict(data.get("mcpServers") or {})
    if server in servers and not force:
        return False
    servers[server] = entry
    data["mcpServers"] = servers
    write_json(path, data)
    return True


def _configure_mcp(
    plugin: dict[str, Any], agent: str, home: Path, *, force: bool, dry_run: bool
) -> PluginResult:
    install = plugin["install"]
    server = str(install["server"])
    entry = install["entry"]
    if not isinstance(entry, dict):
        return PluginResult(plugin["id"], agent, "failed", "install.entry must be a mapping")
    if dry_run:
        return PluginResult(
            plugin["id"], agent, "would_install", f"merge mcpServers.{server} into {agent} config"
        )
    if agent == "opencode":
        # OpenCode uses a `mcp` key with opencode-shaped entries (list command);
        # the addons helper raises LabError on unreadable configs (no clobber).
        from astroai_lab.agent.addons import _cursor_to_opencode, _merge_opencode_mcp_server

        path = home / _OPENCODE_MCP_FILE
        if not force and _mcp_present("opencode", server, home):
            return PluginResult(plugin["id"], agent, "skipped", f"already merged ({path})")
        _merge_opencode_mcp_server(path, server, _cursor_to_opencode(entry), force=True)
        return PluginResult(plugin["id"], agent, "installed", f"mcp.{server} -> {path}")
    if agent == "hermes":
        path = home / _HERMES_MCP_FILE
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                data = {}
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
        servers = dict(data.get("mcpServers") or {})
        if server in servers and not force:
            return PluginResult(plugin["id"], agent, "skipped", f"already merged ({path})")
        servers[server] = entry
        data["mcpServers"] = servers
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return PluginResult(plugin["id"], agent, "installed", f"mcpServers.{server} -> {path}")
    rel = _OPENCLAW_MCP_FILE if agent == "openclaw" else _MCP_JSON_FILES.get(agent)
    if not rel:
        return PluginResult(plugin["id"], agent, "skipped", f"no MCP config for agent {agent}")
    path = home / rel
    merged = _merge_mcp_entry(path, server, entry, force=force)
    if not merged:
        return PluginResult(plugin["id"], agent, "skipped", f"already merged ({path})")
    return PluginResult(plugin["id"], agent, "installed", f"mcpServers.{server} -> {path}")


def _install_config(
    plugin: dict[str, Any], agent: str, home: Path, *, force: bool, dry_run: bool
) -> PluginResult:
    install = plugin["install"]
    target = _expand_home(str(install["target"]), home)
    content = str(install.get("content", ""))
    if target.is_file() and not force:
        return PluginResult(plugin["id"], agent, "skipped", f"already present ({target})")
    if dry_run:
        return PluginResult(plugin["id"], agent, "would_install", str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return PluginResult(plugin["id"], agent, "installed", str(target))


def _install_addon(
    plugin: dict[str, Any], agent: str, home: Path, *, force: bool, dry_run: bool
) -> PluginResult:
    from astroai_lab.agent.addons import add_addon

    addon_id = str(plugin["install"]["addon"])
    result = add_addon(addon_id, home=home, force=force, dry_run=dry_run)
    return PluginResult(plugin["id"], agent, result.status, result.detail)


def _apply(
    plugin: dict[str, Any],
    agent: str,
    home: Path,
    *,
    force: bool,
    dry_run: bool,
) -> PluginResult:
    install = plugin.get("install") or {}
    if install.get("type"):
        # Legacy addon transport — shared dispatcher, identical to `agent add`.
        from astroai_lab.agent.addons import _apply_addon, plugin_as_addon

        result = _apply_addon(plugin_as_addon(plugin), home=home, force=force, dry_run=dry_run)
        status = _addon_status_to_plugin(result.status, dry_run)
        return PluginResult(plugin["id"], agent, status, result.detail)
    kind = plugin["kind"]
    if kind == "skill":
        return _install_skill(plugin, agent, home, force=force, dry_run=dry_run)
    if kind == "mcp":
        return _configure_mcp(plugin, agent, home, force=force, dry_run=dry_run)
    if kind == "config":
        return _install_config(plugin, agent, home, force=force, dry_run=dry_run)
    return _install_addon(plugin, agent, home, force=force, dry_run=dry_run)


def _addon_status_to_plugin(status: str, dry_run: bool) -> str:
    """Map an AddonResult.status to the PluginResult vocabulary."""
    if dry_run and status == "dry-run":
        return "would_install"
    if status in ("installed", "cloned", "updated"):
        return "installed"
    if status in ("skipped", "failed", "no-op"):
        return status
    return status


def install_plugin(
    plugin_id: str,
    *,
    agent: str | None = None,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    installed_only: bool = True,
) -> list[PluginResult]:
    """Install a plugin. Default applies to installed agents in the matrix;
    ``--agent`` scopes to one agent. ``installed_only=False`` (configure) acts
    on the full support matrix."""
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise LabError(f"Unknown plugin: {plugin_id}", hint="astroai-lab agent plugins list")
    home = home or Path.home()
    selected = _selected_agents(plugin, agent)
    if installed_only:
        selected = [a for a in selected if _agent_installed(a, home)]
    if not selected:
        return [PluginResult(plugin_id, "", "skipped", "no installed agent in support matrix")]
    results = []
    for a in selected:
        results.append(_apply(plugin, a, home, force=force, dry_run=dry_run))
    return results


def update_plugin(
    plugin_id: str,
    *,
    agent: str | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> list[PluginResult]:
    """Refresh a plugin: force re-apply to every installed agent in the matrix."""
    return install_plugin(
        plugin_id,
        agent=agent,
        home=home,
        force=True,
        dry_run=dry_run,
        installed_only=True,
    )


def remove_plugin(
    plugin_id: str,
    *,
    agent: str | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> list[PluginResult]:
    """Remove a plugin from the support matrix (or one --agent)."""
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise LabError(f"Unknown plugin: {plugin_id}", hint="astroai-lab agent plugins list")
    home = home or Path.home()
    selected = _selected_agents(plugin, agent)
    results: list[PluginResult] = []
    for a in selected:
        results.append(_remove_from_agent(plugin, a, home, dry_run=dry_run))
    return results


def _remove_from_agent(
    plugin: dict[str, Any], agent: str, home: Path, *, dry_run: bool
) -> PluginResult:
    if (plugin.get("install") or {}).get("type"):
        # Legacy addon transports have no uninstall (bundled / cloned skills).
        return PluginResult(
            plugin["id"],
            agent,
            "no-op",
            "legacy addon has no removal — remove files manually (agent addons)",
        )
    kind = plugin["kind"]
    if kind == "skill":
        dst = _skill_targets(plugin, home).get(agent)
        if dst is None or not (dst / "SKILL.md").is_file():
            return PluginResult(plugin["id"], agent, "skipped", "not installed")
        if dry_run:
            return PluginResult(plugin["id"], agent, "would_remove", str(dst))
        shutil.rmtree(dst)
        return PluginResult(plugin["id"], agent, "removed", str(dst))
    if kind == "mcp":
        server = str(plugin["install"]["server"])
        if not _mcp_present(agent, server, home):
            return PluginResult(plugin["id"], agent, "skipped", "not merged")
        if dry_run:
            return PluginResult(
                plugin["id"], agent, "would_remove", f"mcpServers.{server} from {agent} config"
            )
        if agent == "opencode":
            path = home / _OPENCODE_MCP_FILE
            if path.is_file():
                try:
                    data = read_jsonc(path)
                except (OSError, ValueError):
                    data = {}
                if isinstance(data, dict):
                    mcp = dict(data.get("mcp") or {})
                    mcp.pop(server, None)
                    data["mcp"] = mcp
                    write_json(path, data)
            return PluginResult(plugin["id"], agent, "removed", f"mcp.{server}")
        if agent == "hermes":
            path = home / _HERMES_MCP_FILE
            if path.is_file():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict):
                    servers = dict(data.get("mcpServers") or {})
                    servers.pop(server, None)
                    data["mcpServers"] = servers
                    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            return PluginResult(plugin["id"], agent, "removed", f"mcpServers.{server}")
        rel = _OPENCLAW_MCP_FILE if agent == "openclaw" else _MCP_JSON_FILES.get(agent)
        if not rel:
            return PluginResult(plugin["id"], agent, "skipped", f"no MCP config for agent {agent}")
        path = home / rel
        if path.is_file():
            try:
                data = read_jsonc(path)
            except (OSError, ValueError):
                data = {}
            if isinstance(data, dict):
                servers = dict(data.get("mcpServers") or {})
                servers.pop(server, None)
                data["mcpServers"] = servers
                write_json(path, data)
        return PluginResult(plugin["id"], agent, "removed", f"mcpServers.{server}")
    if kind == "config":
        target = _expand_home(str(plugin["install"]["target"]), home)
        if not target.is_file():
            return PluginResult(plugin["id"], agent, "skipped", "not installed")
        if dry_run:
            return PluginResult(plugin["id"], agent, "would_remove", str(target))
        target.unlink(missing_ok=True)
        return PluginResult(plugin["id"], agent, "removed", str(target))
    # addon kind: legacy transport has no uninstall — tell the user.
    return PluginResult(
        plugin["id"],
        agent,
        "no-op",
        "addon kind has no removal — use `astroai-lab agent remove` for agents",
    )


def configure_plugin(
    plugin_id: str,
    *,
    agent: str | None = None,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> list[PluginResult]:
    """Per-agent config merge (kind: mcp) or config write (kind: config).

    Applies to the full support matrix (or --agent); for skill/addon kinds the
    user is pointed at install/update instead.
    """
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise LabError(f"Unknown plugin: {plugin_id}", hint="astroai-lab agent plugins list")
    home = home or Path.home()
    selected = _selected_agents(plugin, agent)
    results: list[PluginResult] = []
    for a in selected:
        if (plugin.get("install") or {}).get("type"):
            # Legacy addon transport: configure == install (the dispatcher
            # merges cursor/copilot/claude/opencode configs itself).
            results.append(_apply(plugin, a, home, force=force, dry_run=dry_run))
            continue
        kind = plugin["kind"]
        if kind == "mcp":
            results.append(_configure_mcp(plugin, a, home, force=force, dry_run=dry_run))
        elif kind == "config":
            results.append(_install_config(plugin, a, home, force=force, dry_run=dry_run))
        elif kind == "skill":
            results.append(
                PluginResult(plugin_id, a, "no-op", "skills have no config — use `plugins update`")
            )
        else:
            results.append(
                PluginResult(plugin_id, a, "no-op", "addon kind — use `plugins install/update`")
            )
    return results


# ---------------------------------------------------------------------------
# Recursive agent removal (wired into registry._remove_registry_method)
# ---------------------------------------------------------------------------


def remove_agent_plugin_files(
    agent_id: str,
    *,
    home: Path | None = None,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    """Drop every plugin-applied file for one agent (recursive removal).

    Called by ``agent remove <agent>`` so uninstalling an agent also removes
    its plugin-created files. Returns ``RemoveResult``-shaped dicts
    (target / status / detail) for the registry to surface.
    """
    home = home or Path.home()
    results: list[dict[str, str]] = []
    for plugin in load_plugins():
        if agent_id not in plugin.get("agents", []):
            continue
        res = _remove_from_agent(plugin, agent_id, home, dry_run=dry_run)
        # Only surface actionable rows — a plugin the agent never installed
        # would otherwise add a noisy `skipped` line to `agent remove`.
        if res.status in ("removed", "would_remove"):
            results.append(
                {
                    "target": f"plugins:{agent_id}:{plugin['id']}",
                    "status": res.status,
                    "detail": res.detail,
                }
            )
    return results
