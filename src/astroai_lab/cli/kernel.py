from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.core.kernel import list_kernels, register_kernel, unregister_kernel
from astroai_lab.errors import LabError

kernel_app = typer.Typer(help="Jupyter kernel registration (notebook sessions).")


@kernel_app.command("ensure")
def kernel_ensure(
    name: Annotated[str, typer.Option("--name", help="Kernel name.")] = "astroai",
) -> None:
    """Create/refresh a scratch-safe notebook kernel (no pixi project needed).

    Examples:
        astroai-lab kernel ensure
        astroai-lab kernel ensure --name student
    """
    from astroai_lab.core.kernel import ensure_scratch_safe_kernel

    try:
        kname = ensure_scratch_safe_kernel(name=name)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Scratch-safe kernel ready: {kname}")


@kernel_app.command("register")
def kernel_register(
    path: Annotated[Path | None, typer.Argument(help="Project path (default: cwd).")] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
) -> None:
    """Register project as Jupyter kernel.

    Examples:
        astroai-lab kernel register
        astroai-lab kernel register /srcdir/mylab --name mylab
    """
    project = path or Path.cwd()
    try:
        kname = register_kernel(project, name=name)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Kernel registered: {kname}")


@kernel_app.command("list")
def kernel_list(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """List registered kernels.

    Examples:
        astroai-lab kernel list
        astroai-lab kernel list --json
        astroai-lab --json kernel list
    """
    opts = merge_opts(ctx, json_output=json_output)
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
        astroai-lab kernel unregister mylab
    """
    try:
        unregister_kernel(name)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Unregistered {name}")
