from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from astroai_lab.utils.console import console


@dataclass
class DoctorReport:
    work_dir: str
    scratch_dir: str | None
    save_dir: str
    config_dir: str
    home: str
    user_bin: str
    npm_prefix: str
    runtime_root: str
    arc_projects: str | None
    pixi_cache_dir: str | None
    uv_cache_dir: str | None
    home_quota_pct: int | None
    tools: dict[str, bool]
    canfar_auth: str | None = None
    gpu: str | None = None
    hygiene_ok: bool = True
    hygiene_issues: list[str] | None = None


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def _format_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    import re

    lines = []
    for line in text.splitlines():
        # Match lines starting with optional whitespace, followed by a command
        # e.g., "  astroai-lab init mylab" or "  cd target"
        match = re.match(
            r"^(\s*)(astroai-lab|canfar|git|pixi|uv|gh|cd|kilo|goose|cline|eval|setfacl|rsync)\b([^#\n]*)(.*)$",
            line,
        )
        if match:
            indent, cmd, rest, comment = match.groups()
            line_str = f"{indent}[bold #00d7ff]{cmd}{rest}[/bold #00d7ff]"
            if comment:
                line_str += f"[dim]{comment}[/dim]"
            lines.append(line_str)
        else:
            # Inline replacements for backtick block like `command`
            line = re.sub(r"`([^`]+)`", r"[bold #ffaf00]\1[/bold #ffaf00]", line)
            lines.append(line)
    return "\n".join(lines)


def print_error(message: str) -> None:
    formatted = _format_text(message)
    if "\n  " in formatted:
        msg, hint = formatted.split("\n  ", 1)
        console.print(f"[bold red]Error:[/bold red] {msg}")
        console.print(f"[dim]  {hint}[/dim]")
    else:
        console.print(f"[bold red]Error:[/bold red] {formatted}")


def print_ok(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {_format_text(message)}")


def print_hint(message: str) -> None:
    console.print(f"[dim]{_format_text(message)}[/dim]")


def print_info(message: str) -> None:
    console.print(f"[bold #00d7ff]{_format_text(message)}[/bold #00d7ff]")


def print_warn(message: str) -> None:
    console.print(f"[bold yellow]Warning:[/bold yellow] {_format_text(message)}")


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
    table = Table(title="astroai-lab doctor", show_header=True, header_style="bold")
    table.add_column("Key", style="dim")
    table.add_column("Value")
    table.add_row("work_dir", report.work_dir)
    table.add_row("scratch_dir", report.scratch_dir or "(not mounted)")
    table.add_row("save_dir", report.save_dir)
    table.add_row("config_dir", report.config_dir)
    table.add_row("home", report.home)
    table.add_row("user_bin", report.user_bin)
    table.add_row("npm_prefix", report.npm_prefix)
    table.add_row("runtime_root", report.runtime_root)
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
    if report.canfar_auth:
        table.add_row("canfar_auth", report.canfar_auth)
    if report.gpu:
        table.add_row("gpu", report.gpu.splitlines()[0] if report.gpu else "")
    table.add_row("home_hygiene", "[green]ok[/green]" if report.hygiene_ok else "[red]FAIL[/red]")
    console.print(table)

    if report.hygiene_issues:
        print_error("Home-cache hygiene failed (scratch is writable but caches use $HOME):")
        for issue in report.hygiene_issues:
            print_hint(f"  {issue}")
        print_hint(
            '  Fix: eval "$(astroai-lab env export)" && astroai-lab clean home --all-safe --yes'
        )

    tools_table = Table(title="Tools", show_header=True)
    tools_table.add_column("Command")
    tools_table.add_column("Available")
    for name, ok in sorted(report.tools.items()):
        tools_table.add_row(name, "[green]yes[/green]" if ok else "[red]no[/red]")
    console.print(tools_table)


def env_list_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print_hint("No saved environments.")
        print_hint("  astroai-lab save mylab")
        return
    table = Table(title="Saved environments")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Saved")
    table.add_column("Path")
    for row in rows:
        table.add_row(row["name"], row["kind"], row["saved_at"], row["path"])
    console.print(table)


def status_human(
    quotas: list,
    home_rows: list,
    active_project,
    arc_projects: list,
    processes: list[str],
    canfar_auth: str | None = None,
    canfar_sessions: list[str] | None = None,
    gms_groups=None,
    vault=None,
    resources: dict | None = None,
) -> None:
    console.print("[bold]astroai-lab status[/bold]\n")
    if resources:
        mem = resources.get("mem_pct")
        cpu = resources.get("cpu_pct")
        cg = resources.get("cgroup_mem_pct")
        home = resources.get("home") or {}
        scratch = resources.get("scratch") or {}
        bits = []
        if cpu is not None:
            bits.append(f"cpu~{cpu}%")
        if mem is not None:
            bits.append(f"ram {mem}%")
        if cg is not None:
            bits.append(f"cgroup-mem {cg}%")
        if home.get("pct") is not None:
            bits.append(f"home {home['pct']}% ({home.get('source', '?')})")
        if scratch.get("pct") is not None:
            bits.append(f"scratch {scratch['pct']}%")
        gpus = resources.get("gpu") or []
        if gpus:
            bits.append(
                "gpu "
                + ", ".join(f"{g.get('util_pct', '?')}%" for g in gpus[:2])
            )
        if bits:
            console.print("[bold]Session resources:[/bold] " + " · ".join(bits))
            for note in resources.get("notes") or []:
                console.print(f"[dim]  {note}[/dim]")
            console.print("")
    if canfar_auth:
        console.print(f"[bold]CANFAR Authentication:[/bold] {canfar_auth}\n")
    if gms_groups is not None and gms_groups.groups:
        names = ", ".join(gms_groups.groups[:8])
        extra = f" (+{len(gms_groups.groups) - 8} more)" if len(gms_groups.groups) > 8 else ""
        console.print(f"[bold]CADC groups (GMS):[/bold] {names}{extra}\n")
    elif Path("/arc/projects").is_dir() and gms_groups is None:
        console.print(
            "[dim]CADC groups: unavailable (install cadc-groups / run cadc-get-cert)[/dim]\n"
        )
    if active_project is not None:
        q = active_project.quota
        access = getattr(active_project, "access", "?")
        if q is not None:
            console.print(
                f"[bold]Team project (cwd):[/bold] {active_project.path} "
                f"[{access}] — {q.free} free of {q.total} ({q.pct}% used)"
            )
        else:
            console.print(f"[bold]Team project (cwd):[/bold] {active_project.path} [{access}]")
        console.print("")
    elif arc_projects:
        names = ", ".join(f"{p.name}({getattr(p, 'access', '?')})" for p in arc_projects[:6])
        extra = f" (+{len(arc_projects) - 6} more)" if len(arc_projects) > 6 else ""
        console.print(
            f"[dim]cwd not under /arc/projects — accessible team projects: {names}{extra}[/dim]\n"
        )
    elif Path("/arc/projects").is_dir():
        console.print("[dim]No readable team projects under /arc/projects[/dim]\n")
    if arc_projects:
        pt = Table(title="Team projects (/arc/projects)")
        pt.add_column("Project")
        pt.add_column("Access")
        pt.add_column("ACL groups")
        pt.add_column("GMS")
        pt.add_column("Vault groups")
        for p in arc_projects:
            groups = getattr(p, "acl_groups", None) or []
            group_cell = ", ".join(f"{g.name}({g.perms})" for g in groups[:4])
            if len(groups) > 4:
                group_cell += f" (+{len(groups) - 4})"
            gms_cell = (
                "yes"
                if getattr(p, "gms_member", None) is True
                else "no"
                if getattr(p, "gms_member", None) is False
                else "—"
            )
            vault_node = getattr(p, "vault", None)
            if vault_node is not None and vault_node.found:
                vault_groups = ", ".join(
                    g
                    for g in (
                        vault_node.read_group and f"ro:{vault_node.read_group}",
                        vault_node.write_group and f"rw:{vault_node.write_group}",
                    )
                    if g
                )
            else:
                vault_groups = "—"
            name = p.name
            if getattr(p, "is_cwd", False):
                name = f"{name} [cyan](cwd)[/cyan]"
            pt.add_row(
                name,
                getattr(p, "access", "?"),
                group_cell or "—",
                gms_cell,
                vault_groups or "—",
            )
        console.print(pt)
    if vault is not None and vault.nodes:
        extra = [
            node
            for node in vault.nodes
            if node.found and node.name.casefold() not in {p.name.casefold() for p in arc_projects}
        ]
        if extra:
            vt = Table(title="VOSpace vault (extra containers)")
            vt.add_column("Name")
            vt.add_column("Quota")
            vt.add_column("Read group")
            vt.add_column("Write group")
            vt.add_column("GMS")
            for node in extra:
                q = node.quota_line()
                quota_cell = f"{q.used} / {q.total} ({q.pct}%)" if q is not None else "—"
                gms_cell = (
                    "yes" if node.gms_member is True else "no" if node.gms_member is False else "—"
                )
                vt.add_row(
                    node.name,
                    quota_cell,
                    node.read_group or "—",
                    node.write_group or "—",
                    gms_cell,
                )
            console.print(vt)
    if quotas:
        qt = Table(title="Storage quotas")
        qt.add_column("Location")
        qt.add_column("Used")
        qt.add_column("Free")
        qt.add_column("Total")
        qt.add_column("%")
        for q in quotas:
            style = "red" if q.pct >= 95 else "yellow" if q.pct >= 80 else ""
            pct_cell = f"[{style}]{q.pct}%[/{style}]" if style else f"{q.pct}%"
            label = q.label
            if getattr(q, "current", False):
                label = f"{label} [cyan](cwd)[/cyan]"
            qt.add_row(label, q.used, q.free, q.total, pct_cell)
        console.print(qt)
    if home_rows:
        ht = Table(title="Home breakdown")
        ht.add_column("Dir")
        ht.add_column("Size")
        ht.add_column("Notes")
        for d, s, n in home_rows:
            ht.add_row(d, s, n)
        console.print(ht)
    if processes:
        console.print("\n[bold]Top CPU processes[/bold]")
        for line in processes:
            console.print(f"  {line}")
    if canfar_sessions:
        console.print("\n[bold]CANFAR Active Sessions (canfar ps)[/bold]")
        for line in canfar_sessions:
            console.print(f"  {line}")
