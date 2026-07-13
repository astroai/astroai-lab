from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.core.paths import resolve_paths
from astroai_lab.core.storage import stage_data, sync_data
from astroai_lab.errors import LabError

data_app = typer.Typer(help="Move data between /arc and scratch (rsync).")


@data_app.command("stage")
def data_stage(
    ctx: typer.Context,
    source: Annotated[Path, typer.Argument(help="Persistent source path.")],
    target: Annotated[Path | None, typer.Argument(help="Scratch target.")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
    ] = False,
) -> None:
    """Copy persistent storage to scratch for fast I/O.

    Examples:
        astroai-lab data stage /arc/projects/mygroup/data.fits
        astroai-lab data stage /arc/projects/mygroup/survey/ /scratch/survey/
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
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
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
    ] = False,
) -> None:
    """Copy scratch results to persistent storage.

    Examples:
        astroai-lab data sync /scratch/results/ /arc/projects/mygroup/results/
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
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
