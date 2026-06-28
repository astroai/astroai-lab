from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rich.table import Table

from canfar_lab.utils.console import console


@dataclass
class DoctorReport:
    work_dir: str
    scratch_dir: str | None
    save_dir: str
    config_dir: str
    home: str
    arc_projects: str | None
    pixi_cache_dir: str | None
    uv_cache_dir: str | None
    home_quota_pct: int | None
    tools: dict[str, bool]


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def print_error(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")


def print_ok(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")


def print_hint(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")


def print_info(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")


def print_warn(message: str) -> None:
    console.print(f"[yellow]Warning:[/yellow] {message}")


def doctor_human(report: DoctorReport) -> None:
    table = Table(title="canfar-lab doctor", show_header=True, header_style="bold")
    table.add_column("Key", style="dim")
    table.add_column("Value")
    table.add_row("work_dir", report.work_dir)
    table.add_row("scratch_dir", report.scratch_dir or "(not mounted)")
    table.add_row("save_dir", report.save_dir)
    table.add_row("config_dir", report.config_dir)
    table.add_row("home", report.home)
    if report.arc_projects:
        table.add_row("arc_projects", report.arc_projects)
    if report.pixi_cache_dir:
        table.add_row("pixi_cache", report.pixi_cache_dir)
    if report.uv_cache_dir:
        table.add_row("uv_cache", report.uv_cache_dir)
    if report.home_quota_pct is not None:
        pct = report.home_quota_pct
        style = "red" if pct >= 95 else "yellow" if pct >= 80 else ""
        table.add_row("home_quota", f"[{style}]{pct}%[/{style}]" if style else f"{pct}%")
    console.print(table)

    tools_table = Table(title="Tools", show_header=True)
    tools_table.add_column("Command")
    tools_table.add_column("Available")
    for name, ok in sorted(report.tools.items()):
        tools_table.add_row(name, "[green]yes[/green]" if ok else "[red]no[/red]")
    console.print(tools_table)


def env_list_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print_hint("No saved environments.")
        print_hint("  canfar-lab env save mylab")
        return
    table = Table(title="Saved environments")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Saved")
    table.add_column("Path")
    for row in rows:
        table.add_row(row["name"], row["kind"], row["saved_at"], row["path"])
    console.print(table)
