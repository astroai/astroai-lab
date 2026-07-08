"""Backward-compatible env subcommand group (prefer flat save/resume/saves)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts, merge_opts
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
from canfar_lab.shell import hooks_sh_path, profile_sh_path
from canfar_lab.shell.session_env import export_shell

env_app = typer.Typer(help="Save and resume environments (alias: save/resume/saves).")


@env_app.command("export")
def env_export(
    ensure: Annotated[
        bool,
        typer.Option("--ensure/--no-ensure", help="Create cache and runtime directories."),
    ] = True,
) -> None:
    """Print bash export statements for the current CANFAR lab session.

    Examples:
        eval "$(canfar-lab env export)"
    """
    typer.echo(export_shell(ensure=ensure))


@env_app.command("install-shell")
def env_install_shell(
    dest: Annotated[
        Path,
        typer.Argument(help="Destination directory (e.g. /etc/canfar-lab)."),
    ] = Path("/etc/canfar-lab"),
) -> None:
    """Install bundled profile.sh and hooks.sh for login shells.

    Examples:
        canfar-lab env install-shell /etc/canfar-lab
    """
    dest.mkdir(parents=True, exist_ok=True)
    for src in (profile_sh_path(), hooks_sh_path()):
        target = dest / src.name
        shutil.copy2(src, target)
        target.chmod(0o644)
    ui.print_ok(f"Installed shell files -> {dest}")


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
def env_list(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """List saved environments.

    Examples:
        canfar-lab env list
        canfar-lab env list --json
        canfar-lab --json env list
    """
    opts = merge_opts(ctx, json_output=json_output)
    paths = resolve_paths()
    rows = save_rows(paths.save_dir)
    if opts.json:
        ui.print_json(rows)
    else:
        ui.env_list_table(rows)
