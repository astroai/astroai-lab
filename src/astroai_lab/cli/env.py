"""env group: shell environment export (infra).

The flat save/resume/saves commands are the primary interface; the old
env save/resume/list aliases were removed in the 0.3 simplification.
Image builds copy the packaged profile.sh / hooks.sh at build time —
astroai-lab stays an in-session tool only.
"""

from __future__ import annotations

from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.shell.session_env import export_json, export_shell

env_app = typer.Typer(help="Session environment export.")


@env_app.command("export")
def env_export(
    ctx: typer.Context,
    ensure: Annotated[
        bool,
        typer.Option("--ensure/--no-ensure", help="Create cache and runtime directories."),
    ] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Print bash export statements for the current AstroAI lab session.

    With `--json`, prints the resolved session environment as a JSON object
    instead (same keys and values, no shell syntax).

    Examples:
        eval "$(astroai-lab env export)"
        astroai-lab env export --json
        astroai-lab --json env export
    """
    opts = merge_opts(ctx, json_output=json_output)
    if opts.json:
        ui.print_json(export_json(ensure=ensure))
    else:
        typer.echo(export_shell(ensure=ensure))
