from __future__ import annotations

from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import merge_opts
from canfar_lab.core.hygiene import (
    apply_clean,
    collect_cache_targets,
    collect_home_targets,
    format_bytes,
    prune_uv_cache,
)
from canfar_lab.core.paths import resolve_paths

clean_app = typer.Typer(help="Clear re-downloadable caches.")


@clean_app.command("home")
def clean_home(
    ctx: typer.Context,
    all_safe: Annotated[
        bool, typer.Option("--all-safe", help="Stale pkg + ML + xdg junk.")
    ] = False,
    stale_pkg: Annotated[bool, typer.Option("--stale-pkg")] = False,
    ml: Annotated[bool, typer.Option("--ml")] = False,
    hf: Annotated[bool, typer.Option("--hf", help="Hugging Face models (expensive).")] = False,
    xdg_junk: Annotated[bool, typer.Option("--xdg-junk")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
    ] = False,
) -> None:
    """Clear re-downloadable junk under $HOME on /arc.

    Examples:
        canfar-lab clean home --dry-run --all-safe
        canfar-lab clean home --all-safe --yes
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
    if all_safe:
        stale_pkg = ml = xdg_junk = True
    if not any([stale_pkg, ml, hf, xdg_junk]):
        ui.print_error("Specify --all-safe or at least one of --stale-pkg --ml --hf --xdg-junk")
        raise typer.Exit(1)
    paths = resolve_paths()
    targets = collect_home_targets(paths.home, stale_pkg=stale_pkg, ml=ml, hf=hf, xdg_junk=xdg_junk)
    if not targets:
        ui.print_hint("Nothing to clean.")
        return
    for t in targets:
        ui.print_hint(f"  {t.label}: {format_bytes(t.bytes)}")
    total = sum(t.bytes for t in targets)
    if opts.dry_run:
        ui.print_ok(f"dry-run: would free {format_bytes(total)}")
        return
    freed = apply_clean(targets, dry_run=False)
    ui.print_ok(f"Freed {format_bytes(freed)}")


@clean_app.command("cache")
def clean_cache(
    ctx: typer.Context,
    all_safe: Annotated[bool, typer.Option("--all-safe")] = False,
    pip: Annotated[bool, typer.Option("--pip")] = False,
    uv_cache: Annotated[bool, typer.Option("--uv")] = False,
    npm: Annotated[bool, typer.Option("--npm")] = False,
    pixi: Annotated[bool, typer.Option("--pixi")] = False,
    conda: Annotated[bool, typer.Option("--conda")] = False,
    hf: Annotated[bool, typer.Option("--hf")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
    ] = False,
) -> None:
    """Clear scratch download caches.

    Examples:
        canfar-lab clean cache --all-safe
        canfar-lab clean cache --dry-run --pixi --uv
    """
    opts = merge_opts(ctx, dry_run=dry_run, yes=yes)
    if all_safe:
        pip = uv_cache = npm = pixi = conda = True
    if not any([pip, uv_cache, npm, pixi, conda, hf]):
        ui.print_error("Specify --all-safe or individual cache flags.")
        raise typer.Exit(1)
    targets = collect_cache_targets(
        pip=pip, uv_cache=uv_cache, npm=npm, pixi=pixi, conda=conda, hf=hf
    )
    for t in targets:
        ui.print_hint(f"  {t.label}: {format_bytes(t.bytes)}")
    if opts.dry_run:
        ui.print_ok(f"dry-run: would free {format_bytes(sum(t.bytes for t in targets))}")
        if uv_cache:
            ui.print_hint("  `uv cache prune` would also run")
        return
    if uv_cache:
        prune_uv_cache(dry_run=False)
    freed = apply_clean(targets, dry_run=False)
    ui.print_ok(f"Freed {format_bytes(freed)}")
