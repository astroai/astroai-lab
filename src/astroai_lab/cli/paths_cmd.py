"""Session path and tool inventory commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.core.tools import (
    CheckItem,
    ToolInfo,
    checks_as_dicts,
    checks_ok,
    inventory_tools,
    paths_dict,
    run_checks,
    tools_as_dicts,
)
from astroai_lab.utils.console import console


def _paths_human(data: dict[str, str | None]) -> None:
    table = Table(title="astroai-lab paths", show_header=True, header_style="bold")
    table.add_column("Key", style="dim")
    table.add_column("Value")
    for key, value in data.items():
        table.add_row(key, value or "(unset)")
    console.print(table)
    ui.print_hint('  tip: `eval "$(astroai-lab env export)"` refreshes session env vars')


def _tools_human(tools: list[ToolInfo]) -> None:
    table = Table(title="astroai-lab tools", show_header=True, header_style="bold")
    table.add_column("Command")
    table.add_column("Available")
    table.add_column("Path / version")
    for t in tools:
        avail = "[green]yes[/green]" if t.available else "[red]no[/red]"
        detail = t.version or t.path or "—"
        table.add_row(t.name, avail, detail)
    console.print(table)
    missing = [t.name for t in tools if not t.available]
    if missing:
        ui.print_hint(f"  missing: {', '.join(missing)}")
        ui.print_hint("  agents: `astroai-lab agent list`  or  `astroai-lab agent install`")


def _check_human(items: list[CheckItem]) -> None:
    table = Table(title="astroai-lab check", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for item in items:
        status = "[green]ok[/green]" if item.ok else "[red]fail[/red]"
        table.add_row(item.name, status, item.detail)
    console.print(table)


def register(app: typer.Typer) -> None:
    @app.command("paths")
    def paths_cmd(
        ctx: typer.Context,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """Show resolved session paths (work, scratch, caches, saves).

        Examples:
            astroai-lab paths
            astroai-lab paths --json
            astroai-lab --json paths
        """
        opts = merge_opts(ctx, json_output=json_output)
        data = paths_dict()
        if opts.json:
            ui.print_json(data)
            return
        _paths_human(data)

    @app.command("tools")
    def tools_cmd(
        ctx: typer.Context,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """List common session tools and versions on PATH.

        Examples:
            astroai-lab tools
            astroai-lab tools --json
        """
        opts = merge_opts(ctx, json_output=json_output)
        tools = inventory_tools()
        if opts.json:
            ui.print_json({"tools": tools_as_dicts(tools)})
            return
        _tools_human(tools)

    @app.command("check")
    def check_cmd(
        ctx: typer.Context,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
        strict: Annotated[
            bool,
            typer.Option(
                "--strict",
                help="Also require recommended tools (pixi, uv, gh, rg, jq, canfar).",
            ),
        ] = False,
    ) -> None:
        """Quick session health check (paths writable, core tools present).

        Examples:
            astroai-lab check
            astroai-lab check --json
            astroai-lab check --strict
        """
        opts = merge_opts(ctx, json_output=json_output)
        items = run_checks()
        ok = checks_ok(items, strict=strict)
        if opts.json:
            ui.print_json({"ok": ok, "strict": strict, "checks": checks_as_dicts(items)})
            raise typer.Exit(0 if ok else 1)
        _check_human(items)
        if ok:
            ui.print_ok("Session looks healthy")
        else:
            ui.print_error("Session check failed — see rows marked fail")
            ui.print_hint("  astroai-lab doctor --json")
            raise typer.Exit(1)
