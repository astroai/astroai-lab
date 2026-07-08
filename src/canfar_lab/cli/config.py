from __future__ import annotations

from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import merge_opts
from canfar_lab.config.settings import config_file_path, get_settings

config_app = typer.Typer(
    help="Optional preferences (~/.canfar/lab/config.yaml).",
    invoke_without_command=True,
)


@config_app.callback(invoke_without_command=True)
def config_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("Use: `canfar-lab config show` | `canfar-lab config path`")


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Display current lab settings.

    Examples:
        canfar-lab config show
        canfar-lab config show --json
        canfar-lab --json config show
    """
    opts = merge_opts(ctx, json_output=json_output)
    settings = get_settings()
    data = settings.model_dump(mode="json")
    if opts.json:
        ui.print_json(data)
    else:
        for key, val in data.items():
            ui.print_hint(f"  {key}: {val}")


@config_app.command("path")
def config_path_cmd() -> None:
    """Print path to optional config file.

    Examples:
        canfar-lab config path
    """
    typer.echo(str(config_file_path()))
