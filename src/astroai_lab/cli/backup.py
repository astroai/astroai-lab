"""CLI for periodic /srcdir → /arc/home backups."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import get_opts, merge_opts
from astroai_lab.core import backup as backup_mod
from astroai_lab.errors import LabError

backup_app = typer.Typer(help="Back up ephemeral work dir to /arc/home on an interval.")


@backup_app.command("run")
def backup_run(
    ctx: typer.Context,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Force even when home quota is high.")
    ] = False,
) -> None:
    """Run one backup of TMP_SRC_DIR to ~/.astroai/lab/backups/<session>/.

    Examples:
        astroai-lab backup run
        astroai-lab --yes backup run
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
    try:
        status = backup_mod.run_backup(dry_run=opts.dry_run, yes=opts.yes)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(status.__dict__)
        if not status.ok and not status.skipped:
            raise typer.Exit(1)
        return
    if status.skipped:
        ui.print_warn(status.message)
        return
    if opts.dry_run:
        ui.print_ok(f"dry-run: would backup {status.source} -> {status.dest}")
        return
    ui.print_ok(f"Backup -> {status.dest} ({status.duration_sec:.1f}s)")


@backup_app.command("start")
def backup_start(
    ctx: typer.Context,
    interval: Annotated[
        int | None,
        typer.Option("--interval", help="Seconds between backups (default 3600)."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Start even if ASTROAI_LAB_BACKUP_ENABLED=false.")
    ] = False,
) -> None:
    """Start the background backup daemon (idempotent).

    Examples:
        astroai-lab backup start
        astroai-lab backup start --interval 21600
    """
    opts = get_opts(ctx)
    try:
        pid = backup_mod.start_daemon(interval=interval, force=force)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json({"pid": pid, "interval": interval or backup_mod.backup_interval_sec()})
        return
    ui.print_ok(f"Backup daemon running (pid {pid})")


@backup_app.command("stop")
def backup_stop(ctx: typer.Context) -> None:
    """Stop the background backup daemon."""
    opts = get_opts(ctx)
    stopped = backup_mod.stop_daemon()
    if opts.json:
        ui.print_json({"stopped": stopped})
        return
    if stopped:
        ui.print_ok("Backup daemon stopped")
    else:
        ui.print_hint("Backup daemon was not running")


@backup_app.command("status")
def backup_status(ctx: typer.Context) -> None:
    """Show daemon pid and last backup result."""
    opts = get_opts(ctx)
    pid = backup_mod.daemon_running()
    last = backup_mod.load_status()
    payload = {
        "enabled": backup_mod.backup_enabled(),
        "interval": backup_mod.backup_interval_sec(),
        "pid": pid,
        "dest": str(backup_mod.backup_dest()),
        "last": last.__dict__ if last else None,
    }
    if opts.json:
        ui.print_json(payload)
        return
    ui.print_hint(f"  enabled:  {payload['enabled']}")
    ui.print_hint(f"  interval: {payload['interval']}s")
    ui.print_hint(f"  daemon:   {('pid ' + str(pid)) if pid else 'not running'}")
    ui.print_hint(f"  dest:     {payload['dest']}")
    if last:
        state = "ok" if last.ok else ("skipped" if last.skipped else "failed")
        ui.print_hint(f"  last:     {state} at {last.finished_at} ({last.message})")
    else:
        ui.print_hint("  last:     (none)")


@backup_app.command("restore")
def backup_restore(
    ctx: typer.Context,
    from_path: Annotated[
        Path | None, typer.Option("--from", help="Backup directory to restore.")
    ] = None,
    to: Annotated[Path | None, typer.Option("--to", help="Destination work dir.")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Overwrite non-empty destination.")
    ] = False,
) -> None:
    """Restore a backup mirror into the work directory.

    Examples:
        astroai-lab backup restore --yes
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
    try:
        dest = backup_mod.restore_backup(
            source=from_path, dest=to, dry_run=opts.dry_run, yes=opts.yes
        )
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json({"dest": str(dest), "dry_run": opts.dry_run})
        return
    if opts.dry_run:
        ui.print_ok(f"dry-run: would restore -> {dest}")
    else:
        ui.print_ok(f"Restored -> {dest}")


@backup_app.command("loop", hidden=True)
def backup_loop(
    interval: Annotated[
        int | None, typer.Option("--interval", help="Seconds between backups.")
    ] = None,
) -> None:
    """Internal: blocking backup loop for the background daemon."""
    backup_mod.daemon_loop(interval=interval)
