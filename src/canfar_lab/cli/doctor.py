from __future__ import annotations

import shutil
from dataclasses import asdict
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts
from canfar_lab.core.paths import quota_used_pct, resolve_paths

doctor_app = typer.Typer(help="Full session diagnostic.", invoke_without_command=True)
TOOL_NAMES = ("git", "gh", "pixi", "uv", "jq", "rg", "canfar", "rsync", "jupyter")


@doctor_app.callback()
def doctor_cmd(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output."),
    ] = False,
) -> None:
    """Show session paths, quotas, and tool availability.

    Examples:
        canfar-lab doctor
        canfar-lab doctor --json
    """
    if ctx.invoked_subcommand is not None:
        return
    paths = resolve_paths()
    tools = {name: shutil.which(name) is not None for name in TOOL_NAMES}
    canfar_auth = None
    if tools.get("canfar"):
        try:
            from canfar_lab.utils.subprocess import run_capture

            canfar_auth = run_capture(["canfar", "auth", "show"])
        except Exception:
            canfar_auth = "Not authenticated"

    report = ui.DoctorReport(
        work_dir=str(paths.work_dir),
        scratch_dir=str(paths.scratch_dir) if paths.scratch_dir else None,
        save_dir=str(paths.save_dir),
        config_dir=str(paths.config_dir),
        home=str(paths.home),
        user_bin=str(paths.user_bin),
        npm_prefix=str(paths.npm_prefix),
        runtime_root=str(paths.runtime_root),
        arc_projects=str(paths.arc_projects) if paths.arc_projects else None,
        pixi_cache_dir=str(paths.pixi_cache_dir) if paths.pixi_cache_dir else None,
        uv_cache_dir=str(paths.uv_cache_dir) if paths.uv_cache_dir else None,
        home_quota_pct=quota_used_pct(paths.home),
        tools=tools,
        canfar_auth=canfar_auth,
    )
    opts = get_opts(ctx)
    if json_output or opts.json:
        ui.print_json(asdict(report))
        return
    ui.doctor_human(report)
