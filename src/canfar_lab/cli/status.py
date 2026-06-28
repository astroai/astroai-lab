from __future__ import annotations

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts
from canfar_lab.core.paths import find_arc_project_root, resolve_paths
from canfar_lab.core.storage import df_line, home_breakdown, list_arc_projects, top_cpu_processes


def register(app: typer.Typer) -> None:
    @app.command()
    def status(ctx: typer.Context) -> None:
        """Show quotas, home space, and top processes.

        Examples:
            canfar-lab status
            canfar-lab --json status
        """
        opts = get_opts(ctx)
        paths = resolve_paths()
        quotas = []
        if q := df_line(paths.home, "home"):
            quotas.append(q)
        for proj in list_arc_projects()[:8]:
            if q := df_line(proj, proj.name):
                quotas.append(q)
        home_rows = home_breakdown(paths.home)
        proj = find_arc_project_root()
        proj_hint = f"Project cwd: {proj}" if proj else "Not under /arc/projects"
        procs = top_cpu_processes()
        if opts.json:
            ui.print_json(
                {
                    "quotas": [q.__dict__ for q in quotas],
                    "home": home_rows,
                    "project_root": str(proj) if proj else None,
                    "processes": procs,
                }
            )
        else:
            ui.status_human(quotas, home_rows, proj_hint, procs)
