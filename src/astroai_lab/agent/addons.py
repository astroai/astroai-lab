"""Curated installable agent addons (skills, rules, MCP, tools).

Phase 3: the plugin registry (``data/agent/plugins/*.yaml``) is the single
source of truth. ``addons.json`` was migrated into ``plugins/*.yaml``
(entries carry ``addon: true``), so every function here is a thin shim over
``agent.plugins`` — the transports themselves (bundled / github-skill /
github-bundle / github-rule / mcp-snippet / cli-tool / agent-skill) live in
``_apply_addon`` and are also reachable via ``agent plugins install``.

Not a catalog of agents — recommendations that help produce correct, lean code
plus science/data skills useful on AstroAI sessions.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.agent_targets import (
    AGENT_SKILL_DIRS,
    mcp_server_present,
    mcp_target,
    merge_mcp_server,
)
from astroai_lab.agent.agent_targets import cursor_to_opencode as _cursor_to_opencode
from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.agent.install import install_tool, tool_on_path
from astroai_lab.agent.upstream import (
    _refresh_upstream_repo,
    _upstream_cache_root,
    update_github_source,
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


def addon_installed(item: dict[str, Any], home: Path) -> bool:
    install = item.get("install") or {}
    itype = install.get("type")
    addon_id = item["id"]

    if itype == "agent-skill":
        targets = _agent_skill_targets(item, home)
        return bool(targets) and all((t / "SKILL.md").is_file() for t in targets.values())

    if itype == "bundled":
        if addon_id == "astroai-lab-workflow":
            return (home / ".cursor" / "skills" / "astroai-lab-workflow" / "SKILL.md").is_file()
        if addon_id == "token-efficient":
            return (home / ".cursor" / "rules" / "token-efficient.mdc").is_file()
        if addon_id.startswith("mcp-"):
            server = addon_id.removeprefix("mcp-")
            return _mcp_server_present(home, server)
        return False

    if itype == "github-skill":
        name = Path(install["path"]).name
        return (home / ".cursor" / "skills" / name / "SKILL.md").is_file()

    if itype == "github-bundle":
        skills = install.get("skills") or []
        if not skills:
            return False
        # Installed if primary skill present
        name = Path(skills[0]).name
        return (home / ".cursor" / "skills" / name / "SKILL.md").is_file()

    if itype == "github-rule":
        rule = Path(install.get("path", "")).name
        return (home / ".cursor" / "rules" / rule).is_file()

    if itype == "mcp-snippet":
        server = install.get("server", "")
        agents = list(item.get("agents") or [])
        if not server or not agents:
            return False
        return any(mcp_server_present(home, a, server) for a in agents if mcp_target(a))

    if itype == "cli-tool":
        return tool_on_path(install.get("tool", addon_id))

    return False


# Skill directories for agents that use the agentskills.io SKILL.md layout.
# Canonical definition lives in agent_targets; re-exported for callers.
# (Import above: AGENT_SKILL_DIRS)


def _agent_skill_targets(item: dict[str, Any], home: Path) -> dict[str, Path]:
    """Map each configured agent to its skill dir for this addon (known agents only)."""
    install = item.get("install") or {}
    agents = list(install.get("agents") or item.get("agents") or [])
    out: dict[str, Path] = {}
    for agent in agents:
        rel = AGENT_SKILL_DIRS.get(agent)
        if rel:
            out[agent] = home / rel / item["id"]
    return out


def _mcp_server_present(home: Path, server: str) -> bool:
    """Back-compat: True when *any* MCP target already has ``server``."""
    if not server:
        return False
    return any(mcp_server_present(home, agent, server) for agent in ("cursor", "copilot", "claude"))


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

    if not force:
        if agent and itype == "mcp-snippet":
            server = install.get("server", "")
            if server and mcp_server_present(home, agent, server):
                return AddonResult(addon_id, "skipped", "already installed")
        elif addon_installed(item, home):
            return AddonResult(addon_id, "skipped", "already installed")

    if itype == "agent-skill":
        targets = _agent_skill_targets(item, home)
        if agent:
            targets = {k: v for k, v in targets.items() if k == agent}
        if not targets:
            raise LabError(
                f"Addon {addon_id} has no known agent skill targets",
                hint="known agents: " + ", ".join(sorted(AGENT_SKILL_DIRS)),
            )
        src = bundle_root() / "skills" / addon_id
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
        name = Path(install["path"]).name
        result = update_github_source(
            home,
            name,
            install["repo"],
            install["path"],
            force=force,
            dry_run=dry_run,
        )
        return AddonResult(addon_id, result.status, result.detail or result.repo)

    if itype == "github-bundle":
        return _install_github_bundle(item, home=home, force=force, dry_run=dry_run)

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


def _install_github_bundle(
    item: dict[str, Any],
    *,
    home: Path,
    force: bool,
    dry_run: bool,
) -> AddonResult:
    install = item["install"]
    repo = install["repo"]
    skills = list(install.get("skills") or [])
    rules = list(install.get("rules") or [])
    paths = [*skills, *rules]
    if not paths:
        raise LabError(f"Addon {item['id']} bundle has no skills/rules")

    if dry_run:
        return AddonResult(item["id"], "dry-run", f"{repo}: {', '.join(paths)}")

    cache_root = _upstream_cache_root(home, repo)
    status, detail = _refresh_upstream_repo(cache_root, repo, paths)
    if status == "failed":
        return AddonResult(item["id"], "failed", detail)

    installed: list[str] = []
    cache_resolved = cache_root.resolve()
    for rel in skills:
        src = (cache_root / rel).resolve()
        try:
            src.relative_to(cache_resolved)
        except ValueError:
            return AddonResult(item["id"], "failed", f"path escapes cache: {rel}")
        if not (src / "SKILL.md").is_file():
            return AddonResult(item["id"], "failed", f"missing SKILL.md at {rel}")
        name = Path(rel).name
        dst = home / ".cursor" / "skills" / name
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
        installed.append(f"skill:{name}")

    for rel in rules:
        src = (cache_root / rel).resolve()
        try:
            src.relative_to(cache_resolved)
        except ValueError:
            return AddonResult(item["id"], "failed", f"path escapes cache: {rel}")
        if not src.is_file():
            return AddonResult(item["id"], "failed", f"missing rule at {rel}")
        dst = home / ".cursor" / "rules" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        installed.append(f"rule:{src.name}")

    return AddonResult(item["id"], status, "; ".join(installed))


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
