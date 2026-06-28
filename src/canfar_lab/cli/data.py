from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts
from canfar_lab.core.paths import resolve_paths
from canfar_lab.core.storage import stage_data, sync_data
from canfar_lab.errors import LabError

data_app = typer.Typer(help="Move data between /arc and scratch.")


@data_app.command("stage")
def data_stage(
    ctx: typer.Context,
    source: Annotated[Path, typer.Argument(help="Persistent source path.")],
    target: Annotated[Path | None, typer.Argument(help="Scratch target.")] = None,
) -> None:
    """Copy persistent storage to scratch for fast I/O.

    Examples:
        canfar-lab data stage /arc/projects/mygroup/data.fits
        canfar-lab data stage /arc/projects/mygroup/survey/ /scratch/survey/
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    dest = target or (paths.scratch_dir / source.name if paths.scratch_dir else None)
    if dest is None:
        ui.print_error("Scratch not mounted — specify a target path.")
        raise typer.Exit(1)
    try:
        stage_data(source, dest, yes=opts.yes, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.dry_run:
        ui.print_ok(f"dry-run: would stage {source} -> {dest}")
    else:
        ui.print_ok(f"Staged to {dest}")


@data_app.command("sync")
def data_sync(
    ctx: typer.Context,
    source: Annotated[Path, typer.Argument(help="Scratch source path.")],
    target: Annotated[Path, typer.Argument(help="Persistent target path.")],
) -> None:
    """Copy scratch results to persistent storage.

    Examples:
        canfar-lab data sync /scratch/results/ /arc/projects/mygroup/results/
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    try:
        sync_data(source, target, paths.scratch_dir, yes=opts.yes, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.dry_run:
        ui.print_ok(f"dry-run: would sync {source} -> {target}")
    else:
        ui.print_ok(f"Synced to {target}")
