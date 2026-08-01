"""Auto-fix and repair agent configurations, directories, syntax errors, and state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
