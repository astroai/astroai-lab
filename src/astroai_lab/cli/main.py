"""Command-line interface for astroai-lab."""

from __future__ import annotations

from typing import Annotated

import typer

from astroai_lab import __version__
from astroai_lab.cli import init_clone_env
from astroai_lab.cli import status as status_mod
from astroai_lab.cli.agent_cmd import agent_app
from astroai_lab.cli.backup import backup_app
from astroai_lab.cli.banner import show_banner
from astroai_lab.cli.clean import clean_app
from astroai_lab.cli.config import config_app
from astroai_lab.cli.context import GlobalOpts
from astroai_lab.cli.data import data_app
from astroai_lab.cli.doctor import doctor_app
from astroai_lab.cli.env import env_app
from astroai_lab.cli.guide import print_guide
from astroai_lab.cli.kernel import kernel_app
from astroai_lab.cli.notebook_cmd import notebook_app
from astroai_lab.cli.paths_cmd import register as register_paths
from astroai_lab.cli.project import project_app
from astroai_lab.cli.workspace import workspace_app

app = typer.Typer(
    name="astroai-lab",
    help="AstroAI in-session workbench for the CANFAR Science Platform.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
    epilog="Platform client: [bold]canfar[/bold] — https://opencadc.github.io/canfar/",
)

init_clone_env.register(app)
status_mod.register(app)
register_paths(app)
app.add_typer(doctor_app, name="doctor")
app.add_typer(env_app, name="env")
app.add_typer(data_app, name="data")
app.add_typer(backup_app, name="backup")
app.add_typer(clean_app, name="clean")
app.add_typer(config_app, name="config")
app.add_typer(workspace_app, name="workspace")
app.add_typer(kernel_app, name="kernel")
app.add_typer(agent_app, name="agent")
app.add_typer(project_app, name="project")
app.add_typer(notebook_app, name="notebook")

@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Minimal output.")] = False,
    version: Annotated[bool | None, typer.Option("--version", "-V", help="Show version.")] = None,
) -> None:
    """In-session workbench for code, environments, and storage paths."""
    ctx.obj = GlobalOpts(json=json_output, yes=yes, dry_run=dry_run, quiet=quiet)
    if version:
        typer.echo(f"astroai-lab {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        show_banner(json_output=json_output)
        raise typer.Exit()


@app.command()
def guide() -> None:
    """Print session workflow cheat sheet.

    Examples:
        astroai-lab guide
    """
    print_guide()


def main_entry() -> None:
    app()


if __name__ == "__main__":
    main_entry()
