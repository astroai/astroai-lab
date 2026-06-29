from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.agent import free_models as agent_free_models
from canfar_lab.agent import install as agent_install
from canfar_lab.agent import bundles as agent_setup_mod
from canfar_lab.cli.context import get_opts
from canfar_lab.core.paths import user_bin_dir
from canfar_lab.errors import LabError

agent_app = typer.Typer(help="AI agent setup and tool installation.")


@agent_app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("Use: `canfar-lab agent setup` | `canfar-lab agent install --list`")


@agent_app.command("setup")
def agent_setup_cmd(
    ctx: typer.Context,
    bundle: Annotated[list[str] | None, typer.Argument()] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Install MCP, rules, and skills for AI coding agents.

    Examples:
        canfar-lab agent setup
        canfar-lab agent setup cursor claude
    """
    opts = get_opts(ctx)
    try:
        agent_setup_mod.agent_setup(
            mode="install",
            bundles=list(bundle) if bundle else None,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if not opts.dry_run:
        try:
            agent_setup_mod.agent_verify()
        except LabError as exc:
            ui.print_warn(str(exc))
    ui.print_ok("Agent setup complete")
    ui.print_hint("  canfar-lab agent install kilo|goose|cline")
    ui.print_hint("  canfar-lab agent models free")
    ui.print_hint("  canfar-lab init myproject")


@agent_app.command("update")
def agent_update_cmd(ctx: typer.Context) -> None:
    """Refresh agent config and GitHub skills."""
    opts = get_opts(ctx)
    try:
        agent_setup_mod.agent_setup(mode="update", force=True, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok("Agent config updated")


@agent_app.command("project")
def agent_project_cmd(
    ctx: typer.Context,
    path: Annotated[Path | None, typer.Argument()] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Install AGENTS.md and .cursor/ in a project repo."""
    opts = get_opts(ctx)
    project = path or Path.cwd()
    try:
        agent_setup_mod.agent_setup(
            mode="project",
            project_dir=project.resolve(),
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Project templates installed in {project}")


@agent_app.command("verify")
def agent_verify_cmd() -> None:
    """Check agent setup status."""
    try:
        agent_setup_mod.agent_verify()
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    stamp = Path.home() / ".canfar" / "lab" / "agent-setup-stamp"
    if stamp.is_file():
        ui.print_hint(f"  last run: {stamp.read_text().strip()}")
    ui.print_ok("Agent setup OK")


@agent_app.command("list")
def agent_list_cmd(ctx: typer.Context) -> None:
    """List available agent config bundles."""
    opts = get_opts(ctx)
    rows = agent_setup_mod.agent_list_bundles()
    if opts.json:
        ui.print_json(rows)
    else:
        for name, desc in rows.items():
            ui.print_hint(f"  {name}: {desc}")


@agent_app.command("install")
def agent_install_cmd(
    ctx: typer.Context,
    tool: Annotated[str | None, typer.Argument(help="Tool name (see --list).")] = None,
    list_tools: Annotated[bool, typer.Option("--list", "-l", help="List tools.")] = False,
) -> None:
    """Install AI coding tools to $CANFAR_LAB_BIN_DIR (scratch or team project, not $HOME).

    Examples:
        canfar-lab agent install claude
        canfar-lab agent install --list
    """
    if list_tools:
        for name, desc in agent_install.list_tools().items():
            typer.echo(f"  {name:<12} {desc}")
        return
    if not tool:
        ui.print_error("Specify a tool or --list")
        raise typer.Exit(1)
    opts = get_opts(ctx)
    try:
        agent_install.install_tool(tool, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.dry_run:
        ui.print_ok(f"dry-run: would install {tool}")
    else:
        ui.print_ok(f"Installed {tool} → {user_bin_dir()}")
        if tool in ("kilo", "goose", "cline", "opencode", "codex"):
            ui.print_hint("  canfar-lab agent models free")


models_app = typer.Typer(help="Free-tier model presets for open coding agents.")
agent_app.add_typer(models_app, name="models")


@models_app.callback(invoke_without_command=True)
def models_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(agent_free_models.free_models_guide())


@models_app.command("list")
def models_list_cmd(ctx: typer.Context) -> None:
    """List free model presets."""
    opts = get_opts(ctx)
    presets = agent_free_models.list_presets()
    if opts.json:
        ui.print_json(presets)
        return
    for name, meta in presets.items():
        typer.echo(f"  {name:<10} {meta['label']}")
        typer.echo(f"             {meta['description']}")


@models_app.command("free")
def models_free_cmd(
    ctx: typer.Context,
    preset: Annotated[str, typer.Option("--preset", "-p", help="Preset name.")] = "coding",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing configs."),
    ] = False,
) -> None:
    """Apply free-tier model configs for goose, kilo, opencode, codex, cline.

    Examples:
        canfar-lab agent models free
        canfar-lab agent models free --preset long
        export OPENROUTER_API_KEY=sk-or-v1-... && canfar-lab agent models free
    """
    opts = get_opts(ctx)
    try:
        actions = agent_free_models.apply_free_models(
            preset=preset,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    prefix = "would apply" if opts.dry_run else "applied"
    for line in actions:
        ui.print_ok(f"{prefix}: {line}")
    if not opts.dry_run:
        ui.print_hint("  Kilo sign-in: `kilo auth`  (or `/connect` in TUI)")
        ui.print_hint("  OpenRouter key: https://openrouter.ai/keys")
        ui.print_hint("  Full guide: `canfar-lab agent models`")
