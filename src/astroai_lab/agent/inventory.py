"""Inventory: skill/bundle dir scans + config presence/syntax verification.

Extracted from ``bundles.py`` in the Phase 0 decomposition
(docs/agent-rethink-plan.md) — behavior is byte-identical to the original.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.agent.registry import registry_verify_issues
from astroai_lab.utils.json_utils import read_json, read_jsonc


def _rel_home(path: Path, home: Path) -> str:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def _check_json_file(path: Path, home: Path, *, jsonc: bool = False) -> str | None:
    """Return a syntax-issue string, or None if the file parses."""
    try:
        if jsonc:
            read_jsonc(path)
        else:
            read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        kind = "JSONC" if jsonc else "JSON"
        return f"{kind} syntax error in {_rel_home(path, home)}: {exc}"
    return None


def _check_toml_file(path: Path, home: Path) -> str | None:
    try:
        import tomllib  # type: ignore
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return None
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return f"TOML syntax error in {_rel_home(path, home)}: {exc}"
    return None


def _check_yaml_file(path: Path, home: Path) -> str | None:
    try:
        import yaml
    except ImportError:
        return None
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return f"YAML syntax error in {_rel_home(path, home)}: {exc}"
    return None


def verify_config_syntax(home: Path) -> list[str]:
    """Parse existing agent config files; report syntax errors only."""
    issues: list[str] = []
    checks: list[tuple[Path, str]] = [
        (home / ".cursor" / "mcp.json", "jsonc"),
        (home / ".claude.json", "json"),
        (home / ".claude" / "settings.json", "json"),
        (home / ".config" / "opencode" / "opencode.json", "jsonc"),
        (home / ".config" / "kilo" / "kilo.jsonc", "jsonc"),
        (home / ".copilot" / "mcp-config.json", "jsonc"),
        (home / ".codex" / "config.toml", "toml"),
        (home / ".marimo.toml", "toml"),
        (home / ".config" / "goose" / "config.yaml", "yaml"),
        (home / ".qoder" / "settings.json", "json"),
    ]
    for path, kind in checks:
        if not path.is_file():
            continue
        if kind == "json":
            err = _check_json_file(path, home, jsonc=False)
        elif kind == "jsonc":
            err = _check_json_file(path, home, jsonc=True)
        elif kind == "toml":
            err = _check_toml_file(path, home)
        else:
            err = _check_yaml_file(path, home)
        if err:
            issues.append(err)
    return issues


def verify_setup(home: Path, *, probe_binaries: bool = False) -> list[str]:
    """Presence + content checks, then syntax validation of configs that exist.

    ``probe_binaries`` is off by default so ``agent list`` / status reports stay
    fast; ``agent verify`` turns it on to exercise installed CLIs.
    """
    issues: list[str] = []
    # Syntax first — broken configs often look "empty" to content checks.
    issues.extend(verify_config_syntax(home))

    mcp = home / ".cursor" / "mcp.json"
    if mcp.is_file():
        try:
            data = read_jsonc(mcp)
            if isinstance(data, dict) and not data.get("mcpServers"):
                issues.append("Cursor MCP empty (~/.cursor/mcp.json)")
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    else:
        issues.append("Cursor MCP not configured (~/.cursor/mcp.json)")

    skill = home / ".cursor" / "skills" / "astroai-lab-workflow" / "SKILL.md"
    if not skill.is_file():
        issues.append("Cursor astroai-lab-workflow skill missing")

    claude = home / ".claude.json"
    if claude.is_file():
        try:
            data = read_json(claude)
            if not data.get("mcpServers"):
                issues.append("Claude MCP empty (~/.claude.json)")
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    oc = home / ".config" / "opencode" / "opencode.json"
    if oc.is_file():
        try:
            data = read_jsonc(oc)
            if isinstance(data, dict) and not data.get("mcp"):
                issues.append("OpenCode MCP empty (~/.config/opencode/opencode.json)")
            if isinstance(data, dict):
                from astroai_lab.agent.opencode_config import opencode_config_issues

                issues.extend(opencode_config_issues(data))
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    goose_cfg = home / ".config" / "goose" / "config.yaml"
    if goose_cfg.is_file():
        try:
            text = goose_cfg.read_text(encoding="utf-8")
            if "GOOSE_PROVIDER:" not in text or "GOOSE_MODEL:" not in text:
                issues.append("Goose provider not fully configured (~/.config/goose/config.yaml)")
        except OSError:
            pass

    marimo = home / ".marimo.toml"
    if marimo.is_file():
        try:
            if "openrouter" not in marimo.read_text(encoding="utf-8"):
                issues.append(
                    "marimo.toml missing OpenRouter config — run: astroai-lab agent setup marimo"
                )
        except OSError:
            pass

    # Phase 1 registry: verify config of installed registered agents only, so
    # fresh images without hermes/openclaw don't fail the container gate.
    issues.extend(registry_verify_issues(home, installed_only=True, probe_binaries=probe_binaries))

    return issues


def list_skills_inventory(home: Path | None = None) -> list[dict[str, Any]]:
    """Inventory of bundled + upstream skills and anything already under ~/.cursor/skills."""
    root = bundle_root()
    home = home or Path.home()
    sources_path = root / "skills-sources.json"
    catalog: dict[str, dict[str, Any]] = {}

    if sources_path.is_file():
        data = read_json(sources_path)
        for item in data.get("local_skills", []):
            name = item["name"]
            catalog[name] = {
                "name": name,
                "source": "bundled",
                "repo": "",
                "path": f"cursor/skills/{name}",
                "homepage": "",
                "note": item.get("note", ""),
            }
        for item in data.get("upstream_skills", []):
            name = item["name"]
            catalog[name] = {
                "name": name,
                "source": "github",
                "repo": item["repo"],
                "path": item["path"],
                "homepage": item.get("homepage", f"https://github.com/{item['repo']}"),
                "note": "",
            }
        for name in data.get("pixi_skills_only", []):
            catalog[name] = {
                "name": name,
                "source": "pixi-skills",
                "repo": "",
                "path": "",
                "homepage": data.get("pixi_skills", {}).get(
                    "homepage", "https://github.com/pavelzw/pixi-skills"
                ),
                "note": "install via pixi-skills, not agent update",
            }

    skills_dir = home / ".cursor" / "skills"
    installed_names: set[str] = set()
    if skills_dir.is_dir():
        for skill_md in skills_dir.glob("*/SKILL.md"):
            installed_names.add(skill_md.parent.name)

    rows: list[dict[str, Any]] = []
    for name, meta in catalog.items():
        installed = name in installed_names
        rows.append(
            {
                **meta,
                "installed": installed,
                "skill_path": str(skills_dir / name) if installed else "",
            }
        )

    for name in sorted(installed_names - set(catalog)):
        rows.append(
            {
                "name": name,
                "source": "extra",
                "repo": "",
                "path": "",
                "homepage": "",
                "note": "present under ~/.cursor/skills but not in skills-sources.json",
                "installed": True,
                "skill_path": str(skills_dir / name),
            }
        )

    rows.sort(key=lambda r: (0 if r["source"] == "bundled" else 1, r["name"]))
    return rows


def list_bundles() -> dict[str, str]:
    manifest = bundle_root() / "manifest.json"
    if not manifest.is_file():
        return {}
    data = read_json(manifest)
    return {k: v.get("description", "") for k, v in data.get("bundles", {}).items()}
