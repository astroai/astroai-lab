"""Curated installable agent addons (skills, rules, MCP, tools).

Not a catalog of agents — recommendations that help produce correct, lean code
plus science/data skills useful on AstroAI sessions.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.agent.bundles import (
    _refresh_upstream_repo,
    _upstream_cache_root,
    update_github_source,
)
from astroai_lab.agent.install import install_tool, tool_on_path
from astroai_lab.errors import LabError
from astroai_lab.utils.json_utils import read_json, read_jsonc, write_json


@dataclass(frozen=True)
class AddonResult:
    id: str
    status: str
    detail: str = ""


def load_addons() -> list[dict[str, Any]]:
    path = bundle_root() / "addons.json"
    if not path.is_file():
        return []
    data = read_json(path)
    return list(data.get("addons", []))


def get_addon(addon_id: str) -> dict[str, Any] | None:
    for item in load_addons():
        if item.get("id") == addon_id:
            return item
    return None


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
        return _mcp_server_present(home, install.get("server", ""))

    if itype == "cli-tool":
        return tool_on_path(install.get("tool", addon_id))

    return False


def _mcp_server_present(home: Path, server: str) -> bool:
    if not server:
        return False
    cursor = home / ".cursor" / "mcp.json"
    if cursor.is_file():
        try:
            data = read_jsonc(cursor)
            if isinstance(data, dict) and server in (data.get("mcpServers") or {}):
                return True
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return False


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
            hint="astroai-lab agent addons",
        )
    home = home or Path.home()
    install = item.get("install") or {}
    itype = install.get("type")

    if itype == "bundled":
        return AddonResult(
            addon_id,
            "skipped",
            install.get("note") or "bundled — run: astroai-lab agent setup",
        )

    if not force and addon_installed(item, home):
        return AddonResult(addon_id, "skipped", "already installed")

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
        return _install_mcp_snippet(item, home=home, force=force, dry_run=dry_run)

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
            hint="astroai-lab agent addons",
        )
    return [
        add_addon(aid, home=home, force=force, dry_run=dry_run) for aid in ordered
    ]


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
) -> AddonResult:
    install = item["install"]
    server = install["server"]
    cursor_cfg = install.get("cursor") or {}
    opencode_cfg = install.get("opencode") or {}

    if dry_run:
        return AddonResult(item["id"], "dry-run", f"mcp:{server}")

    # Cursor + Copilot share mcpServers shape
    for rel in (
        home / ".cursor" / "mcp.json",
        home / ".copilot" / "mcp-config.json",
    ):
        _merge_cursor_mcp(rel, server, cursor_cfg, force=force)

    # Claude
    _merge_claude_mcp(home / ".claude.json", server, cursor_cfg, force=force)

    # OpenCode
    oc = home / ".config" / "opencode" / "opencode.json"
    oc_cfg = opencode_cfg or _cursor_to_opencode(cursor_cfg)
    _merge_opencode_mcp_server(oc, server, oc_cfg, force=force)

    return AddonResult(item["id"], "installed", f"mcp:{server}")


def _cursor_to_opencode(cfg: dict[str, Any]) -> dict[str, Any]:
    cmd = cfg.get("command")
    args = cfg.get("args") or []
    if not cmd:
        return {}
    out: dict[str, Any] = {
        "type": "local",
        "command": [cmd, *args],
        "enabled": True,
    }
    if cfg.get("env"):
        out["environment"] = cfg["env"]
    return out


def _merge_cursor_mcp(
    path: Path, server: str, cfg: dict[str, Any], *, force: bool
) -> None:
    if not cfg:
        return
    if path.is_file():
        try:
            data = read_jsonc(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise LabError(
                f"Cannot merge MCP into unreadable config: {path}",
                hint=f"Fix JSON syntax first (`astroai-lab agent verify`): {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise LabError(f"MCP config must be a JSON object: {path}")
    else:
        data = {"mcpServers": {}}
    servers = dict(data.get("mcpServers") or {})
    if server in servers and not force:
        return
    servers[server] = cfg
    data["mcpServers"] = servers
    write_json(path, data)


def _merge_claude_mcp(
    path: Path, server: str, cfg: dict[str, Any], *, force: bool
) -> None:
    if not cfg:
        return
    if path.is_file():
        try:
            data = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise LabError(
                f"Cannot merge MCP into unreadable ~/.claude.json: {path}",
                hint=f"Fix JSON syntax first (`astroai-lab agent verify`): {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise LabError(f"Claude config must be a JSON object: {path}")
    else:
        data = {}
    servers = dict(data.get("mcpServers") or {})
    if server in servers and not force:
        return
    servers[server] = cfg
    data["mcpServers"] = servers
    write_json(path, data)


def _merge_opencode_mcp_server(
    path: Path, server: str, cfg: dict[str, Any], *, force: bool
) -> None:
    if not cfg:
        return
    if path.is_file():
        try:
            data = read_jsonc(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise LabError(
                f"Cannot merge MCP into unreadable OpenCode config: {path}",
                hint=f"Fix JSON syntax first (`astroai-lab agent verify`): {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise LabError(f"OpenCode config must be a JSON object: {path}")
    else:
        data = {}
    mcp = dict(data.get("mcp") or {})
    if server in mcp and not force:
        return
    mcp[server] = cfg
    data["mcp"] = mcp
    write_json(path, data)
