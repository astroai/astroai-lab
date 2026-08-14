"""Install transports for agent plugins (skills, rules, MCP, tools).

Plugin YAML under ``data/agent/plugins/*.yaml`` is the catalog. This module
applies those entries (bundled / github-skill / github-bundle / github-rule /
mcp-snippet / cli-tool / agent-skill) via ``_apply_addon``, also used by
``agent plugins install``.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.agent_targets import (
    AGENT_SKILL_DIRS,
    MCP_TARGETS,
    mcp_server_present,
    mcp_target,
    merge_mcp_server,
    skill_path,
)
from astroai_lab.agent.agent_targets import cursor_to_opencode as _cursor_to_opencode
from astroai_lab.agent.bundle_path import bundled_skill_src
from astroai_lab.agent.install import install_tool, tool_on_path
from astroai_lab.agent.upstream import (
    _refresh_upstream_repo,
    _upstream_cache_root,
)
from astroai_lab.errors import LabError


@dataclass(frozen=True)
class AddonResult:
    id: str
    status: str
    detail: str = ""


def plugin_as_addon(plugin: dict[str, Any]) -> dict[str, Any]:
    """Map a plugin registry entry to the legacy addon dict shape.

    The Phase 3 skill schema (``install.source`` + ``install.targets``, no
    ``install.type``) is the legacy ``agent-skill`` transport; synthesize the
    ``type`` + ``agents`` so the addon transports below stay byte-identical.
    """
    install = dict(plugin.get("install") or {})
    if plugin["kind"] == "skill" and "type" not in install:
        install["type"] = "agent-skill"
        install["agents"] = list(plugin.get("agents", []))
    return {
        "id": plugin["id"],
        "kind": plugin["kind"],
        "tags": plugin.get("tags", []),
        "summary": plugin.get("summary", ""),
        "homepage": plugin.get("homepage", ""),
        "default": bool(plugin.get("default")),
        "agents": list(plugin.get("agents", [])),
        "install": install,
    }


def load_addons() -> list[dict[str, Any]]:
    """Every plugin registry entry marked ``addon: true`` (legacy catalog)."""
    from astroai_lab.agent.plugins import load_plugins

    return [plugin_as_addon(p) for p in load_plugins() if p.get("addon")]


def get_addon(addon_id: str) -> dict[str, Any] | None:
    from astroai_lab.agent.plugins import get_plugin

    plugin = get_plugin(addon_id)
    if plugin is None or not plugin.get("addon"):
        return None
    return plugin_as_addon(plugin)


def list_addons(
    *,
    kind: str | None = None,
    tag: str | None = None,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    home = home or Path.home()
    rows: list[dict[str, Any]] = []
    for item in load_addons():
        if kind and item.get("kind") != kind:
            continue
        tags = item.get("tags") or []
        if tag and tag not in tags:
            continue
        rows.append(
            {
                "id": item["id"],
                "kind": item.get("kind", ""),
                "tags": tags,
                "summary": item.get("summary", ""),
                "homepage": item.get("homepage", ""),
                "default": bool(item.get("default")),
                "installed": addon_installed(item, home),
            }
        )
    return rows


def addon_installed(item: dict[str, Any], home: Path, agent: str | None = None) -> bool:
    install = item.get("install") or {}
    itype = install.get("type")
    addon_id = item["id"]

    if itype == "agent-skill":
        targets = _agent_skill_targets(item, home, agent=agent)
        return bool(targets) and all((t / "SKILL.md").is_file() for t in targets.values())

    if itype == "bundled":
        if addon_id == "token-efficient":
            return (home / ".cursor" / "rules" / "token-efficient.mdc").is_file()
        if addon_id.startswith("mcp-"):
            server = addon_id.removeprefix("mcp-")
            return _mcp_server_present(home, server, agent=agent)
        return False

    if itype == "github-skill":
        name = Path(install["path"]).name
        dests = _skill_dests(item, home, name, agent=agent)
        return bool(dests) and all((p / "SKILL.md").is_file() for p in dests.values())

    if itype == "github-bundle":
        skills = install.get("skills") or []
        if not skills:
            return False
        name = Path(skills[0]).name
        dests = _skill_dests(item, home, name, agent=agent)
        return bool(dests) and all((p / "SKILL.md").is_file() for p in dests.values())

    if itype == "github-rule":
        rule = Path(install.get("path", "")).name
        return (home / ".cursor" / "rules" / rule).is_file()

    if itype == "mcp-snippet":
        server = install.get("server", "")
        agents = [agent] if agent else list(item.get("agents") or [])
        hosts = [a for a in agents if mcp_target(a)]
        if not server or not hosts:
            return False
        return all(mcp_server_present(home, a, server) for a in hosts)

    if itype == "cli-tool":
        return tool_on_path(install.get("tool", addon_id))

    return False


# Skill directories for agents that use the agentskills.io SKILL.md layout.
# Canonical definition lives in agent_targets; re-exported for callers.
# (Import above: AGENT_SKILL_DIRS)


def _matrix_agents(item: dict[str, Any], agent: str | None = None) -> list[str]:
    install = item.get("install") or {}
    agents = list(install.get("agents") or item.get("agents") or [])
    if agent:
        return [a for a in agents if a == agent]
    return agents


def _agent_skill_targets(
    item: dict[str, Any], home: Path, agent: str | None = None
) -> dict[str, Path]:
    """Map each configured agent to its skill dir for this addon (known agents only)."""
    return _skill_dests(item, home, item["id"], agent=agent)


def _skill_dests(
    item: dict[str, Any], home: Path, name: str, agent: str | None = None
) -> dict[str, Path]:
    """Skill install paths for one agent, or every skill-host in the matrix."""
    out: dict[str, Path] = {}
    for ag in _matrix_agents(item, agent):
        dst = skill_path(home, ag, name)
        if dst is not None:
            out[ag] = dst
    return out


def _mcp_server_present(home: Path, server: str, agent: str | None = None) -> bool:
    """True when the given agent (or every MCP host, if omitted) has ``server``."""
    if not server:
        return False
    agents = [agent] if agent else list(MCP_TARGETS)
    return all(mcp_server_present(home, a, server) for a in agents)


def add_addon(
    addon_id: str,
    *,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> AddonResult:
    item = get_addon(addon_id)
    if item is None:
        raise LabError(
            f"Unknown addon: {addon_id}",
            hint="astroai-lab agent plugins list",
        )
    return _apply_addon(item, home=home, force=force, dry_run=dry_run)


def _apply_addon(
    item: dict[str, Any],
    *,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    agent: str | None = None,
) -> AddonResult:
    """Apply one addon (plugin-as-addon dict) via its install transport.

    ``agent`` scopes mcp-snippet (and similar) writes to one support-matrix
    agent; omit it to apply every agent listed on the plugin.
    """
    addon_id = item["id"]
    home = home or Path.home()
    install = item.get("install") or {}
    itype = install.get("type")

    if itype == "bundled":
        return AddonResult(
            addon_id,
            "skipped",
            install.get("note") or "bundled — run: astroai-lab agent setup",
        )

    if not force and addon_installed(item, home, agent=agent):
        return AddonResult(addon_id, "skipped", "already installed")

    if itype == "agent-skill":
        targets = _agent_skill_targets(item, home, agent=agent)
        if not targets:
            raise LabError(
                f"Addon {addon_id} has no known agent skill targets",
                hint="known agents: " + ", ".join(sorted(AGENT_SKILL_DIRS)),
            )
        src = bundled_skill_src(str(install.get("source") or addon_id))
        if not (src / "SKILL.md").is_file():
            raise LabError(f"Addon {addon_id} missing bundled SKILL.md at {src}")
        if dry_run:
            return AddonResult(addon_id, "dry-run", ", ".join(sorted(targets)))
        installed: list[str] = []
        for ag, dst in sorted(targets.items()):
            if dst.exists():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            installed.append(f"{ag}:{dst}")
        return AddonResult(addon_id, "installed", "; ".join(installed))

    if itype == "github-skill":
        return _install_github_skill(item, home=home, force=force, dry_run=dry_run, agent=agent)

    if itype == "github-bundle":
        return _install_github_bundle(item, home=home, force=force, dry_run=dry_run, agent=agent)

    if itype == "github-rule":
        return _install_github_rule(item, home=home, force=force, dry_run=dry_run)

    if itype == "mcp-snippet":
        return _install_mcp_snippet(item, home=home, force=force, dry_run=dry_run, agent=agent)

    if itype == "cli-tool":
        tool = install.get("tool")
        if not tool:
            raise LabError(f"Addon {addon_id} missing install.tool")
        if dry_run:
            return AddonResult(addon_id, "dry-run", f"would install CLI {tool}")
        install_tool(tool, dry_run=False)
        return AddonResult(addon_id, "installed", tool)

    raise LabError(f"Addon {addon_id} has unsupported install type: {itype}")


def add_addons(
    ids: list[str] | None = None,
    *,
    tag: str | None = None,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> list[AddonResult]:
    home = home or Path.home()
    selected: list[str] = []
    if tag:
        selected.extend(r["id"] for r in list_addons(tag=tag, home=home) if not r.get("default"))
    if ids:
        selected.extend(ids)
    # de-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for aid in selected:
        if aid not in seen:
            seen.add(aid)
            ordered.append(aid)
    if not ordered:
        raise LabError(
            "Specify addon id(s) or --tag",
            hint="astroai-lab agent plugins list",
        )
    return [add_addon(aid, home=home, force=force, dry_run=dry_run) for aid in ordered]


def _copy_skill_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _src_in_cache(cache_root: Path, rel: str) -> Path | str:
    """Resolve ``rel`` under the cache, or return an error string if it escapes."""
    cache_resolved = cache_root.resolve()
    src = (cache_root / rel).resolve()
    try:
        src.relative_to(cache_resolved)
    except ValueError:
        return f"path escapes cache: {rel}"
    return src


def _install_github_skill(
    item: dict[str, Any],
    *,
    home: Path,
    force: bool,
    dry_run: bool,
    agent: str | None = None,
) -> AddonResult:
    install = item["install"]
    name = Path(install["path"]).name
    dests = _skill_dests(item, home, name, agent=agent)
    if not dests:
        return AddonResult(item["id"], "skipped", "no skill target for this agent")
    pending = {ag: dst for ag, dst in dests.items() if force or not (dst / "SKILL.md").is_file()}
    if not pending:
        return AddonResult(item["id"], "skipped", "already installed")
    if dry_run:
        return AddonResult(item["id"], "dry-run", ", ".join(sorted(pending)))

    cache_root = _upstream_cache_root(home, install["repo"])
    status, detail = _refresh_upstream_repo(cache_root, install["repo"], install["path"])
    if status == "failed":
        return AddonResult(item["id"], "failed", detail)
    src = _src_in_cache(cache_root, install["path"])
    if isinstance(src, str):
        return AddonResult(item["id"], "failed", src)
    if not (src / "SKILL.md").is_file():
        return AddonResult(item["id"], "failed", f"missing SKILL.md at {install['path']}")
    installed: list[str] = []
    for ag, dst in sorted(pending.items()):
        _copy_skill_tree(src, dst)
        installed.append(ag)
    return AddonResult(item["id"], "installed", f"{name} → {', '.join(installed)}")


def _install_github_bundle(
    item: dict[str, Any],
    *,
    home: Path,
    force: bool,
    dry_run: bool,
    agent: str | None = None,
) -> AddonResult:
    install = item["install"]
    repo = install["repo"]
    skills = list(install.get("skills") or [])
    rules = list(install.get("rules") or [])
    paths = [*skills, *rules]
    if not paths:
        raise LabError(f"Addon {item['id']} bundle has no skills/rules")

    agents = _matrix_agents(item, agent)
    if dry_run:
        hosts = ", ".join(agents)
        return AddonResult(item["id"], "dry-run", f"{repo}: {', '.join(paths)} → {hosts}")

    cache_root = _upstream_cache_root(home, repo)
    status, detail = _refresh_upstream_repo(cache_root, repo, paths)
    if status == "failed":
        return AddonResult(item["id"], "failed", detail)

    installed: list[str] = []
    for rel in skills:
        src = _src_in_cache(cache_root, rel)
        if isinstance(src, str):
            return AddonResult(item["id"], "failed", src)
        if not (src / "SKILL.md").is_file():
            return AddonResult(item["id"], "failed", f"missing SKILL.md at {rel}")
        name = Path(rel).name
        for ag in agents:
            dst = skill_path(home, ag, name)
            if dst is None:
                continue
            if not force and (dst / "SKILL.md").is_file():
                continue
            _copy_skill_tree(src, dst)
            installed.append(f"skill:{ag}/{name}")

    # Cursor rules (.mdc) are not SKILL.md — only write them for cursor.
    if "cursor" in agents:
        for rel in rules:
            src = _src_in_cache(cache_root, rel)
            if isinstance(src, str):
                return AddonResult(item["id"], "failed", src)
            if not src.is_file():
                return AddonResult(item["id"], "failed", f"missing rule at {rel}")
            dst = home / ".cursor" / "rules" / src.name
            if dst.is_file() and not force:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            installed.append(f"rule:{src.name}")

    if not installed and not force:
        return AddonResult(item["id"], "skipped", "already installed")
    return AddonResult(item["id"], "installed", "; ".join(installed))


def _install_github_rule(
    item: dict[str, Any],
    *,
    home: Path,
    force: bool,
    dry_run: bool,
) -> AddonResult:
    install = item["install"]
    repo = install["repo"]
    path = install["path"]
    if dry_run:
        return AddonResult(item["id"], "dry-run", path)

    cache_root = _upstream_cache_root(home, repo)
    status, detail = _refresh_upstream_repo(cache_root, repo, path)
    if status == "failed":
        return AddonResult(item["id"], "failed", detail)

    src = cache_root / path
    if not src.is_file():
        return AddonResult(item["id"], "failed", f"missing rule at {path}")
    dst = home / ".cursor" / "rules" / src.name
    if dst.is_file() and not force:
        return AddonResult(item["id"], "skipped", "already installed")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return AddonResult(item["id"], status, str(dst))


def _install_mcp_snippet(
    item: dict[str, Any],
    *,
    home: Path,
    force: bool,
    dry_run: bool,
    agent: str | None = None,
) -> AddonResult:
    install = item["install"]
    server = install["server"]
    cursor_cfg = install.get("cursor") or {}
    opencode_cfg = install.get("opencode") or {}
    agents = list(item.get("agents") or [])
    if not agents:
        raise LabError(
            f"Addon {item['id']} mcp-snippet requires a non-empty agents support matrix",
            hint="Declare agents: [cursor, ...] on the plugin YAML",
        )
    if agent is not None:
        if agent not in agents:
            return AddonResult(
                item["id"], "skipped", f"{agent} not in support matrix ({', '.join(agents)})"
            )
        agents = [agent]

    if dry_run:
        return AddonResult(item["id"], "dry-run", f"mcp:{server} → {', '.join(agents)}")

    written: list[str] = []
    for ag in agents:
        if mcp_target(ag) is None:
            continue
        entry = opencode_cfg or _cursor_to_opencode(cursor_cfg) if ag == "opencode" else cursor_cfg
        if not entry:
            continue
        if merge_mcp_server(home, ag, server, entry, force=force):
            written.append(ag)
    if not written and not force:
        return AddonResult(item["id"], "skipped", f"mcp:{server} already present")
    detail = f"mcp:{server}" + (f" → {', '.join(written)}" if written else "")
    return AddonResult(item["id"], "installed", detail)


def _merge_cursor_mcp(path: Path, server: str, cfg: dict[str, Any], *, force: bool) -> None:
    """Test/compat shim — prefer ``merge_mcp_server`` for new code."""
    if not cfg:
        return
    # Infer agent from path when possible; fall back to raw file merge.
    home = path.parent.parent if path.name == "mcp.json" else path.parent
    agent = "cursor"
    if path.name == "mcp-config.json":
        agent = "copilot"
        home = path.parent.parent
    elif path.name == ".claude.json":
        agent = "claude"
        home = path.parent
    merge_mcp_server(home, agent, server, cfg, force=force)


def _merge_claude_mcp(path: Path, server: str, cfg: dict[str, Any], *, force: bool) -> None:
    if not cfg:
        return
    merge_mcp_server(path.parent, "claude", server, cfg, force=force)


def _merge_opencode_mcp_server(
    path: Path, server: str, cfg: dict[str, Any], *, force: bool
) -> None:
    if not cfg:
        return
    # path is ~/.config/opencode/opencode.json → home is parents[2]
    home = path.parent.parent.parent
    merge_mcp_server(home, "opencode", server, cfg, force=force)
