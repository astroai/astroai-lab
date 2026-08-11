"""Auto-fix and repair agent configurations, directories, syntax errors, and state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.clean_agent import clean_agent_state
from astroai_lab.agent.setup_state import failed_path
from astroai_lab.utils.json_utils import read_jsonc, write_json


@dataclass(frozen=True)
class FixResult:
    target: str
    fixed: bool
    detail: str


def fix_agent_setup(*, home: Path | None = None, dry_run: bool = False) -> list[FixResult]:
    """Inspect and auto-repair common agent config issues.

    Fixes broken syntax, missing folders, and stale locks.
    """
    home = home or Path.home()
    results: list[FixResult] = []

    # 1. Clean stale locks & failed markers
    cleans = clean_agent_state(home=home, stale_locks=True, failed_marker=True, dry_run=dry_run)
    for c in cleans:
        results.append(
            FixResult(
                target=c.target, fixed=(c.status in ("removed", "would_remove")), detail=c.detail
            )
        )

    # 2. Ensure directories exist
    dirs_to_create = [
        home / ".cursor" / "skills",
        home / ".cursor" / "rules",
        home / ".config" / "opencode",
        home / ".config" / "kilo",
        home / ".config" / "goose",
        home / ".codex",
        home / ".astroai" / "lab",
    ]
    for d in dirs_to_create:
        if not d.is_dir():
            if dry_run:
                results.append(
                    FixResult(target=d.name, fixed=True, detail=f"Would create directory {d}")
                )
            else:
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    results.append(
                        FixResult(target=d.name, fixed=True, detail=f"Created directory {d}")
                    )
                except OSError as exc:
                    results.append(
                        FixResult(target=d.name, fixed=False, detail=f"Failed creating {d}: {exc}")
                    )

    # 3. Check and repair JSON/JSONC syntax in config files
    json_configs = [
        home / ".cursor" / "mcp.json",
        home / ".config" / "opencode" / "opencode.json",
        home / ".config" / "kilo" / "kilo.jsonc",
        home / ".claude.json",
    ]
    for cfg in json_configs:
        if not cfg.is_file():
            continue
        try:
            parsed = read_jsonc(cfg)
            if not isinstance(parsed, dict):
                raise ValueError("JSON root must be an object")
        except (OSError, ValueError) as exc:
            # File is corrupted - attempt repair or reset
            if dry_run:
                results.append(
                    FixResult(
                        target=cfg.name, fixed=True, detail=f"Would repair syntax in {cfg}: {exc}"
                    )
                )
            else:
                try:
                    # Write valid default JSON
                    default_obj = {"mcpServers": {}} if "mcp" in cfg.name else {}
                    write_json(cfg, default_obj)
                    results.append(
                        FixResult(
                            target=cfg.name, fixed=True, detail=f"Repaired broken JSON in {cfg}"
                        )
                    )
                except OSError as write_err:
                    results.append(
                        FixResult(
                            target=cfg.name,
                            fixed=False,
                            detail=f"Failed repairing {cfg}: {write_err}",
                        )
                    )

    # If failed marker exists and no issues remain, unlink it
    fpath = failed_path(home)
    if fpath.is_file() and not dry_run:
        fpath.unlink(missing_ok=True)

    return results


def repair_installed_agents(*, home: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Repair shared setup plus every installed registry agent's config.

    Used by bare ``agent repair`` and ``agent verify --fix``.
    """
    from astroai_lab.agent.registry import fix_registry_agent, list_installed_registry_agents
    from astroai_lab.errors import LabError

    home = home or Path.home()
    setup_results = fix_agent_setup(home=home, dry_run=dry_run)
    actions: list[str] = []
    errors: list[str] = []
    fixed: list[str] = []
    agents = list_installed_registry_agents(home)
    for agent in agents:
        aid = agent["id"]
        try:
            result = fix_registry_agent(aid, home=home, dry_run=dry_run)
        except LabError as exc:
            errors.append(f"{aid}: {exc}")
            continue
        actions.extend(result["actions"])
        errors.extend(result["errors"])
        # Only count agents that actually changed something (not "healthy" no-ops).
        changed = any(
            any(tok in a for tok in ("created ", "repaired ", "would create", "would repair"))
            for a in result["actions"]
        )
        if result["ok"] and changed:
            fixed.append(aid)
    return {
        "ok": not errors,
        "partial": bool(actions) and bool(errors),
        "setup": setup_results,
        "agents": [a["id"] for a in agents],
        "fixed": fixed,
        "actions": actions,
        "errors": errors,
    }
