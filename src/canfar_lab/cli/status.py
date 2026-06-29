import shutil
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

        canfar_auth = None
        canfar_sessions = None
        if shutil.which("canfar") is not None:
            try:
                from canfar_lab.utils.subprocess import run_capture
                canfar_auth = run_capture(["canfar", "auth", "show"])
            except Exception:
                canfar_auth = "Not authenticated"
            try:
                from canfar_lab.utils.subprocess import run_capture
                canfar_sessions = run_capture(["canfar", "ps"]).splitlines()
            except Exception:
                pass

        if opts.json:
            ui.print_json(
                {
                    "quotas": [q.__dict__ for q in quotas],
                    "home": home_rows,
                    "project_root": str(proj) if proj else None,
                    "processes": procs,
                    "canfar_auth": canfar_auth,
                    "canfar_sessions": canfar_sessions,
                }
            )
        else:
            ui.status_human(
                quotas,
                home_rows,
                proj_hint,
                procs,
                canfar_auth=canfar_auth,
                canfar_sessions=canfar_sessions,
            )
