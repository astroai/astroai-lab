from __future__ import annotations

import shutil
from dataclasses import asdict
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import get_opts
from astroai_lab.core.home_hygiene import check_home_cache_hygiene
from astroai_lab.core.paths import quota_used_pct, resolve_paths
from astroai_lab.shell.session_env import resolve_session_env

doctor_app = typer.Typer(help="Full session diagnostic.", invoke_without_command=True)
TOOL_NAMES = ("git", "gh", "pixi", "uv", "jq", "rg", "canfar", "rsync", "jupyter", "nvidia-smi")


@doctor_app.callback()
def doctor_cmd(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output."),
    ] = False,
) -> None:
    """Show session paths, quotas, tools, and home-cache hygiene.

    Exit code 1 when /scratch is writable but package caches still target $HOME.

    Examples:
        astroai-lab doctor
        astroai-lab doctor --json
    """
    if ctx.invoked_subcommand is not None:
        return
    paths = resolve_paths()
    session = resolve_session_env(ensure=False)
    tools = {name: shutil.which(name) is not None for name in TOOL_NAMES}
    canfar_auth = None
    if tools.get("canfar"):
        try:
            from astroai_lab.utils.subprocess import run_capture

            canfar_auth = run_capture(["canfar", "auth", "show"])
        except Exception:
            canfar_auth = "Not authenticated"

    gpu = None
    if tools.get("nvidia-smi"):
        try:
            from astroai_lab.utils.subprocess import run_capture

            gpu = run_capture(["nvidia-smi", "-L"]).strip() or "present"
        except Exception:
            gpu = "nvidia-smi failed"

    hygiene = check_home_cache_hygiene(
        home=paths.home,
        scratch=paths.scratch_dir,
        env=session.exports(),
    )
    hygiene_issues = [f"{i.kind}: {i.detail}" for i in hygiene]

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
        gpu=gpu,
        hygiene_ok=len(hygiene_issues) == 0,
        hygiene_issues=hygiene_issues,
    )
    opts = get_opts(ctx)
    if json_output or opts.json:
        ui.print_json(asdict(report))
    else:
        ui.doctor_human(report)
    if hygiene_issues:
        raise typer.Exit(1)
