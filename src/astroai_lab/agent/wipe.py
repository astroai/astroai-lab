"""Full factory-reset wipe of the agent layer (`agent wipe`).

Removes EVERY installed agent (binary + config + plugins + home dirs), the
``~/.astroai/lab`` setup state (stamps, locks, logs), and the Cursor agent
configs (skills / rules / mcp.json) so a user can restart from scratch.

Deliberately scoped: saved environments (~/.astroai/lab/saves/), preferences
(~/.astroai/lab/config.yaml), project files, and CANFAR client config are NOT
touched — only the agent-layer state (per-agent binaries/configs/plugins, the
setup stamp/failed/lock/log markers, Cursor configs, and the upstream-skill
cache) is removed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from astroai_lab.agent.setup_state import (
    failed_path,
    lab_state_dir,
    lock_path,
    log_path,
    stamp_path,
)
from astroai_lab.errors import LabError


def wipe_agent_state(*, home: Path | None = None, dry_run: bool = False) -> list[dict]:
    """Remove every agent binary/config/plugin plus shared agent state.

    Returns a flat list of ``{target, status, detail}`` rows (JSON-friendly,
    same shape as the per-agent remove results). ``dry_run=True`` reports
    ``would_remove`` without touching the filesystem.
    """
    from astroai_lab.agent.install import TOOLS, uninstall_tool
    from astroai_lab.agent.registry import registry_ids, remove_registry_agent

    home = home or Path.home()
    results: list[dict] = []

    # 1. Every agent in the list (YAML under data/agent/agents/). purge=True
    #    drops home config dirs; clean_home=True also clears user-owned $HOME CLIs.
    registered = registry_ids()
    ids = sorted(registered | set(TOOLS))
    for agent_id in ids:
        try:
            if agent_id in registered:
                rows = remove_registry_agent(
                    agent_id, home=home, purge=True, clean_home=True, dry_run=dry_run
                )
            else:
                rows = [
                    r.__dict__
                    for r in uninstall_tool(
                        agent_id, home=home, purge=True, clean_home=True, dry_run=dry_run
                    )
                ]
        except LabError as exc:
            results.append({"target": f"agent:{agent_id}", "status": "error", "detail": str(exc)})
            continue
        results.extend(rows)

    def _rm(path: Path, target: str) -> None:
        """Remove a file or tree, or report would_remove in dry-run."""
        if not (path.exists() or path.is_symlink()):
            return
        if dry_run:
            results.append({"target": target, "status": "would_remove", "detail": str(path)})
            return
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
            results.append({"target": target, "status": "removed", "detail": str(path)})
        except OSError as exc:
            results.append({"target": target, "status": "error", "detail": str(exc)})

    # 2. Agent setup state files under ~/.astroai/lab (stamp / failed marker /
    #    lock / log). The dir itself is preserved while it holds user data
    #    (env saves under saves/, preferences config.yaml); only an
    #    otherwise-empty lab dir is removed for a clean slate.
    for state_file, target in (
        (stamp_path(home), "state:stamp"),
        (failed_path(home), "state:failed"),
        (lock_path(home), "state:lock"),
        (log_path(home), "state:log"),
    ):
        _rm(state_file, target)
    _lab = lab_state_dir(home)
    if _lab.is_dir() and not any(_lab.iterdir()):
        _rm(_lab, "state:astroai-lab")

    # 3. Cursor agent configs (shared across agents, not owned by one registry
    #    entry): skills, rules, and the MCP server manifest — the whole dir.
    _rm(home / ".cursor", "cursor")

    # 4. Upstream skill clone cache (re-cloned by `agent update`).
    _rm(home / ".cache" / "astroai-lab" / "upstream-skills", "cache:upstream-skills")

    # 5. Shared agent files under ~/.astroai/lab (keep saves/ and config.yaml).
    lab = home / ".astroai" / "lab"
    for name in ("agent-env.sh", "agent-tools-reminder.sh"):
        _rm(lab / name, f"config:{name}")
    _rm(home / ".claude.json", "config:.claude.json")

    return results
