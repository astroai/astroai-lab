from __future__ import annotations

from pathlib import Path

from canfar_lab.core.git import git_status
from canfar_lab.core.paths import quota_used_pct, resolve_paths
from canfar_lab.core.project import detect_project, list_saves
from canfar_lab.core.storage import arc_project_statuses


def show_banner(*, json_output: bool = False) -> None:
    from canfar_lab import ui

    paths = resolve_paths()
    git = git_status()
    saves = list_saves(paths.save_dir)
    cwd = Path.cwd()
    project_kind = detect_project(cwd)
    home_pct = quota_used_pct(paths.home)
    active_arc, _, _, _ = arc_project_statuses(cwd, vault=False)

    if json_output:
        ui.print_json(
            {
                "work_dir": str(paths.work_dir),
                "scratch_dir": str(paths.scratch_dir) if paths.scratch_dir else None,
                "save_dir": str(paths.save_dir),
                "saves_count": len(saves),
                "git_dirty": git.uncommitted if git.in_repo else None,
                "project": project_kind.value if project_kind else None,
                "home_quota_pct": home_pct,
                "arc_project": (
                    {
                        "name": active_arc.name,
                        "path": str(active_arc.path),
                        "access": active_arc.access,
                        "quota_pct": active_arc.quota.pct if active_arc.quota else None,
                        "quota_free": active_arc.quota.free if active_arc.quota else None,
                    }
                    if active_arc
                    else None
                ),
            }
        )
        return

    ui.print_info("[bold]canfar-lab[/bold] — in-session workbench")
    ui.print_hint(f"  work:    {paths.work_dir}")
    ui.print_hint(f"  scratch: {paths.scratch_dir or '(not mounted)'}")
    ui.print_hint(f"  saves:   {len(saves)} in {paths.save_dir}")
    if active_arc is not None:
        q = active_arc.quota
        if q is not None:
            ui.print_hint(
                f"  team:    {active_arc.path} [{active_arc.access}] "
                f"({q.free} free of {q.total}, {q.pct}% used)"
            )
        else:
            ui.print_hint(f"  team:    {active_arc.path} [{active_arc.access}]")
    if home_pct is not None and home_pct >= 80:
        ui.print_warn(f"  home quota: {home_pct}% — `canfar-lab clean home --all-safe` to free space")
    if git.in_repo and git.uncommitted:
        ui.print_warn("  uncommitted changes — `git add -A && git commit -m 'session work'`")
    if project_kind:
        ui.print_hint(f"  project: {project_kind.value} in {cwd.name}")
        ui.print_hint("  next: `canfar-lab save`  ·  `canfar-lab push` before closing")
    elif str(cwd).startswith(str(paths.work_dir)):
        ui.print_hint("  next: `canfar-lab init mylab`  ·  `canfar-lab clone owner/repo`")
    else:
        ui.print_hint("  next: `cd` into your project or `canfar-lab guide`")
    ui.print_hint("  help: `canfar-lab guide`")
