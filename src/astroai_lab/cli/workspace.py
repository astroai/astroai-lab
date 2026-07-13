from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import get_opts
from astroai_lab.core.paths import resolve_paths
from astroai_lab.core.workspace import restore_workspace, save_workspace
from astroai_lab.errors import LabError

workspace_app = typer.Typer(help="Freeze/restore full project trees for offline batch.")


@workspace_app.command("save")
def workspace_save(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument()] = None,
    with_cache: Annotated[bool, typer.Option("--with-cache")] = False,
    to: Annotated[Path | None, typer.Option("--to")] = None,
) -> None:
    """Freeze project tree as zstd bundle.

    Examples:
        astroai-lab workspace save mylab
        astroai-lab workspace save mylab --with-cache
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    cwd = Path.cwd()
    bundle_name = name or cwd.name
    try:
        with ui.progress_task("Freezing workspace...", quiet=opts.quiet):
            dest = save_workspace(cwd, paths.work_dir, bundle_name, with_cache=with_cache, dest=to)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Workspace saved -> {dest}")


@workspace_app.command("restore")
def workspace_restore(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()],
    from_path: Annotated[Path | None, typer.Option("--from")] = None,
    to: Annotated[Path | None, typer.Option("--to")] = None,
) -> None:
    """Restore frozen workspace bundle.

    Examples:
        astroai-lab workspace restore mylab
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    try:
        with ui.progress_task("Restoring workspace...", quiet=opts.quiet):
            dest = restore_workspace(paths.work_dir, name, from_path=from_path, target=to)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Restored in {dest}")
