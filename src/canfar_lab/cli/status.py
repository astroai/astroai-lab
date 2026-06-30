import shutil
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import merge_opts
from canfar_lab.core.paths import resolve_paths
from canfar_lab.core.storage import (
    arc_project_dict,
    arc_project_statuses,
    collect_status_quotas,
    home_breakdown,
    top_cpu_processes,
)
from canfar_lab.core.vospace_status import vault_status_dict


def register(app: typer.Typer) -> None:
    @app.command()
    def status(
        ctx: typer.Context,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """Show quotas, home space, team project membership, and top processes.

        Examples:
            canfar-lab status
            canfar-lab status --json
            canfar-lab --json status
        """
        opts = merge_opts(ctx, json_output=json_output)
        paths = resolve_paths()
        active_project, arc_projects, gms, vault = arc_project_statuses()
        quotas = collect_status_quotas(home=paths.home, scratch=paths.scratch_dir)
        seen_quota_labels = {q.label for q in quotas}
        arc_names = {p.name.casefold() for p in arc_projects}
        for proj in arc_projects:
            if proj.vault is not None and proj.vault.found:
                if q := proj.vault.quota_line(current=proj.is_cwd):
                    if q.label not in seen_quota_labels:
                        quotas.append(q)
                        seen_quota_labels.add(q.label)
        if vault is not None:
            for node in vault.nodes:
                if not node.found or node.name.casefold() in arc_names:
                    continue
                if q := node.quota_line():
                    if q.label not in seen_quota_labels:
                        quotas.append(q)
                        seen_quota_labels.add(q.label)
        home_rows = home_breakdown(paths.home)
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
                    "arc_project": (
                        arc_project_dict(active_project) if active_project else None
                    ),
                    "arc_projects": [arc_project_dict(p) for p in arc_projects],
                    "gms_groups": (
                        {"groups": gms.groups, "source": gms.source} if gms else None
                    ),
                    "vault": vault_status_dict(vault),
                    "processes": procs,
                    "canfar_auth": canfar_auth,
                    "canfar_sessions": canfar_sessions,
                }
            )
        else:
            ui.status_human(
                quotas,
                home_rows,
                active_project,
                arc_projects,
                procs,
                canfar_auth=canfar_auth,
                canfar_sessions=canfar_sessions,
                gms_groups=gms,
                vault=vault,
            )
