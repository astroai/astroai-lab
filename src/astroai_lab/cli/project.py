from __future__ import annotations

from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.core.team import init_team_project, project_layout, project_quota_line
from astroai_lab.errors import LabError

project_app = typer.Typer(help="Team workspaces under /arc/projects.")


@project_app.command("init")
def project_init(
    name: Annotated[str, typer.Argument(help="Team workspace name.")],
    members: Annotated[
        str | None, typer.Option("--members", help="Comma-separated usernames.")
    ] = None,
) -> None:
    """Create team workspace layout under /arc/projects.

    Examples:
        astroai-lab project init mygroup
        astroai-lab project init mygroup --members alice,bob
    """
    member_list = [m.strip() for m in members.split(",")] if members else None
    try:
        proj = init_team_project(name, members=member_list)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Project workspace: {proj}")
    for row in project_layout(proj):
        ui.print_hint(f"  {row}")
    quota = project_quota_line(proj, name)
    if quota:
        ui.print_hint(f"  quota: {quota}")
    ui.print_hint("  astroai-lab data stage /arc/projects/.../data/...")
    ui.print_hint("  astroai-lab save mylab --to /arc/projects/.../env-saves/mylab")
