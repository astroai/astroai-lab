from __future__ import annotations

from pathlib import Path

from canfar_lab.agent import bundle_root
from canfar_lab.agent.bundles import (
    default_bundle_names,
    ensure_agent_dirs,
    list_bundles,
    run_bundle,
    verify_setup,
    write_stamp,
)
from canfar_lab.errors import LabError


def agent_setup(
    *,
    mode: str = "install",
    bundles: list[str] | None = None,
    project_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    root = bundle_root()
    home = Path.home()
    names = bundles or default_bundle_names(root)
    if mode == "project":
        names = ["project"]
    ensure_agent_dirs(home, dry_run=dry_run)
    for name in names:
        run_bundle(name, root, home, project_dir, force=force, dry_run=dry_run)
    write_stamp(home, mode, dry_run=dry_run)


def agent_verify() -> None:
    issues = verify_setup(Path.home())
    if issues:
        raise LabError("Agent setup incomplete:\n  " + "\n  ".join(issues))


def agent_list_bundles() -> dict[str, str]:
    return list_bundles()
