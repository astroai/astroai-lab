"""Backward-compatible env subcommand group (prefer flat save/resume/saves)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts
from canfar_lab.core.paths import resolve_paths
from canfar_lab.core.project import (
    format_dir_size,
    require_project,
    resolve_save_dir,
    restore_env,
    save_env,
    save_rows,
)
from canfar_lab.errors import LabError

env_app = typer.Typer(help="Save and resume environments (alias: save/resume/saves).")


@env_app.command("save")
def env_save(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument()] = None,
    to: Annotated[Path | None, typer.Option("--to")] = None,
    full: Annotated[bool, typer.Option("--full")] = False,
) -> None:
    """Save lockfiles for current project.

    Examples:
        canfar-lab env save mylab
    """
    paths = resolve_paths()
    cwd = Path.cwd()
    save_name = name or cwd.name
    save_dir = to or paths.save_dir / save_name
    try:
        require_project(cwd)
        save_env(save_name, save_dir, cwd, full=full)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Saved '{save_name}' -> {save_dir} ({format_dir_size(save_dir)})")


@env_app.command("resume")
def env_resume(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()],
    target: Annotated[Path | None, typer.Argument()] = None,
    from_path: Annotated[Path | None, typer.Option("--from")] = None,
) -> None:
    """Restore saved environment.

    Examples:
        canfar-lab env resume mylab
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    dest = target or paths.work_dir / name
    try:
        save_dir = resolve_save_dir(name, paths.save_dir, from_path)
        with ui.progress_task("Restoring...", quiet=opts.quiet):
            restore_env(save_dir, dest)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Restored in {dest}")


@env_app.command("list")
def env_list(ctx: typer.Context) -> None:
    """List saved environments.

    Examples:
        canfar-lab env list --json
    """
    opts = get_opts(ctx)
    paths = resolve_paths()
    rows = save_rows(paths.save_dir)
    if opts.json:
        ui.print_json(rows)
    else:
        ui.env_list_table(rows)
