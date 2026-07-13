from __future__ import annotations

from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.config.settings import config_file_path, get_settings

config_app = typer.Typer(
    help="Optional preferences (~/.astroai/lab/config.yaml).",
    invoke_without_command=True,
)


@config_app.callback(invoke_without_command=True)
def config_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("Use: `astroai-lab config show` | `astroai-lab config path`")


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Display current lab settings.

    Examples:
        astroai-lab config show
        astroai-lab config show --json
        astroai-lab --json config show
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
        astroai-lab config path
    """
    typer.echo(str(config_file_path()))
