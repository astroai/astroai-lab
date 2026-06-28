from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from rich.progress import Progress, SpinnerColumn, TextColumn
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


@contextmanager
def progress_task(description: str, *, quiet: bool = False) -> Iterator[None]:
    if quiet:
        yield
        return
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description, total=None)
        yield


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
        print_hint("  canfar-lab save mylab")
        return
    table = Table(title="Saved environments")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Saved")
    table.add_column("Path")
    for row in rows:
        table.add_row(row["name"], row["kind"], row["saved_at"], row["path"])
    console.print(table)


def status_human(quotas: list, home_rows: list, project_hint: str, processes: list[str]) -> None:
    console.print("[bold]canfar-lab status[/bold]\n")
    if quotas:
        qt = Table(title="Quotas (/arc)")
        qt.add_column("Location")
        qt.add_column("Used")
        qt.add_column("Total")
        qt.add_column("%")
        for q in quotas:
            style = "red" if q.pct >= 95 else "yellow" if q.pct >= 80 else ""
            pct_cell = f"[{style}]{q.pct}%[/{style}]" if style else f"{q.pct}%"
            qt.add_row(q.label, q.used, q.total, pct_cell)
        console.print(qt)
    if home_rows:
        ht = Table(title="Home breakdown")
        ht.add_column("Dir")
        ht.add_column("Size")
        ht.add_column("Notes")
        for d, s, n in home_rows:
            ht.add_row(d, s, n)
        console.print(ht)
    if project_hint:
        console.print(f"\n[dim]{project_hint}[/dim]")
    if processes:
        console.print("\n[bold]Top CPU processes[/bold]")
        for line in processes:
            console.print(f"  {line}")
