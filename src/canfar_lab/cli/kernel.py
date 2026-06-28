from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.core.kernel import list_kernels, register_kernel, unregister_kernel
from canfar_lab.errors import LabError

kernel_app = typer.Typer(help="Jupyter kernel registration (notebook sessions).")


@kernel_app.command("register")
def kernel_register(
    path: Annotated[Path | None, typer.Argument(help="Project path (default: cwd).")] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
) -> None:
    """Register project as Jupyter kernel.

    Examples:
        canfar-lab kernel register
        canfar-lab kernel register /srcdir/mylab --name mylab
    """
    project = path or Path.cwd()
    try:
        kname = register_kernel(project, name=name)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Kernel registered: {kname}")


@kernel_app.command("list")
def kernel_list(ctx: typer.Context) -> None:
    """List registered kernels.

    Examples:
        canfar-lab kernel list
    """
    from canfar_lab.cli.context import get_opts

    opts = get_opts(ctx)
    rows = list_kernels()
    if opts.json:
        ui.print_json(rows)
    else:
        for row in rows:
            ui.print_hint(f"  {row['name']}: {row['path']}")


@kernel_app.command("unregister")
def kernel_unregister(name: Annotated[str, typer.Argument()]) -> None:
    """Remove a registered kernel.

    Examples:
        canfar-lab kernel unregister mylab
    """
    try:
        unregister_kernel(name)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Unregistered {name}")
