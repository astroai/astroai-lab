from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.agent import bundles as agent_setup_mod
from astroai_lab.agent import free_models as agent_free_models
from astroai_lab.agent import install as agent_install
from astroai_lab.cli.context import get_opts
from astroai_lab.core.paths import user_bin_dir
from astroai_lab.errors import LabError

agent_app = typer.Typer(help="AI agent setup and tool installation.")


@agent_app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint(
            "Use: `astroai-lab agent setup` | `astroai-lab agent sync` | "
            "`astroai-lab agent sources update`"
        )


@agent_app.command("setup")
def agent_setup_cmd(
    ctx: typer.Context,
    bundle: Annotated[list[str] | None, typer.Argument()] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Install MCP, rules, and skills for AI coding agents.

    Examples:
        astroai-lab agent setup
        astroai-lab agent setup cursor claude
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
    ui.print_hint("  astroai-lab agent install kilo|goose|cline")
    ui.print_hint("  astroai-lab agent models free")
    ui.print_hint("  astroai-lab init myproject")


@agent_app.command("update")
def agent_update_cmd(ctx: typer.Context) -> None:
    """Refresh agent MCP, rules, skills, and GitHub skill clones.

    Run after an AstroAI image upgrade so ~/.cursor skills match current
    astroai-lab workflow (paths, upgrade-cadc-tools, CLI flags).

    Examples:
        astroai-lab agent update
    """
    _run_agent_sync(ctx)


@agent_app.command("sync", hidden=True)
def agent_sync_cmd(ctx: typer.Context) -> None:
    """Alias for ``agent update``."""
    _run_agent_sync(ctx)


@agent_app.command("status")
def agent_status_cmd(ctx: typer.Context) -> None:
    """Show which agents are installed, configured, and have issues."""
    import shutil

    opts = get_opts(ctx)
    home = Path.home()
    agents = [
        ("opencode", "opencode", home / ".config" / "opencode" / "opencode.json"),
        ("claude", "claude", home / ".claude.json"),
        ("goose", "goose", home / ".config" / "goose" / "config.yaml"),
        ("kilo", "kilo", home / ".config" / "kilo" / "kilo.jsonc"),
        ("codex", "codex", home / ".codex" / "config.toml"),
        ("copilot", "copilot", home / ".copilot" / "mcp-config.json"),
        ("cline", "cline", home / ".config" / "canfar" / "lab" / "cline-free.md"),
    ]
    rows = []
    for name, binary, config_path in agents:
        installed = shutil.which(binary) is not None
        has_config = config_path.is_file()
        rows.append(
            {
                "agent": name,
                "binary": installed,
                "config": has_config,
                "config_path": str(config_path),
            }
        )
    if opts.json:
        ui.print_json(rows)
        return
    ui.print_hint("  Agent        Binary    Config")
    ui.print_hint("  ─────────    ───────   ──────")
    for row in rows:
        b = "✓" if row["binary"] else "✗"
        c = "✓" if row["config"] else "—"
        ui.print_hint(f"  {row['agent']:<12} {b:<9} {c}")
    issues = agent_setup_mod.verify_setup(home)
    if issues:
        ui.print_hint("")
        for issue in issues:
            ui.print_warn(f"  {issue}")
    stamp = home / ".astroai" / "lab" / "agent-setup-stamp"
    if stamp.is_file():
        ui.print_hint("")
        ui.print_hint(f"  Last setup: {stamp.read_text().strip()}")


def _run_agent_sync(ctx: typer.Context) -> None:
    opts = get_opts(ctx)
    try:
        results = agent_setup_mod.agent_sync(dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if not opts.dry_run:
        try:
            agent_setup_mod.agent_verify()
        except LabError as exc:
            ui.print_warn(str(exc))
    prefix = "would refresh" if opts.dry_run else "refreshed"
    for result in results:
        if result.status == "skipped":
            continue
        ui.print_ok(f"{prefix} skill {result.name} ({result.repo}: {result.status})")
    ui.print_ok("Agent config updated")


sources_app = typer.Typer(help="GitHub upstream skill sources (see skills-sources.json).")
agent_app.add_typer(sources_app, name="sources")


@sources_app.callback(invoke_without_command=True)
def sources_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("Use: `astroai-lab agent sources list` | `astroai-lab agent sources update`")


@sources_app.command("list")
def sources_list_cmd(ctx: typer.Context) -> None:
    """List configured GitHub skill sources and local cache paths."""
    opts = get_opts(ctx)
    home = Path.home()
    rows = []
    for item in agent_setup_mod.list_github_sources():
        cache = agent_setup_mod.upstream_cache_path(home, item["repo"])
        installed = home / ".cursor" / "skills" / item["name"] / "SKILL.md"
        rows.append(
            {
                **item,
                "cache": str(cache),
                "cached": (cache / ".git").is_dir(),
                "installed": installed.is_file(),
            }
        )
    if opts.json:
        ui.print_json(rows)
        return
    for row in rows:
        state = "installed" if row["installed"] else "missing"
        cache_state = "cached" if row["cached"] else "not cached"
        ui.print_hint(f"  {row['name']:<28} {row['repo']}  ({state}, {cache_state})")
        ui.print_hint(f"    {row['homepage']}")


@sources_app.command("update")
def sources_update_cmd(ctx: typer.Context) -> None:
    """Pull all GitHub upstream skill sources and refresh ~/.cursor/skills copies.

    Examples:
        astroai-lab agent sources update
        astroai-lab agent sources update --dry-run
    """
    opts = get_opts(ctx)
    try:
        results = agent_setup_mod.update_all_github_sources(force=True, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    prefix = "would update" if opts.dry_run else "updated"
    failures = 0
    for result in results:
        if result.status == "failed":
            failures += 1
            ui.print_error(f"{result.name}: {result.detail}")
        elif result.status != "skipped":
            ui.print_ok(f"{prefix} {result.name} ({result.repo}: {result.status})")
    if failures:
        raise typer.Exit(1)
    ui.print_ok("GitHub skill sources refreshed")


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
    stamp = Path.home() / ".astroai" / "lab" / "agent-setup-stamp"
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
    """Install AI coding tools to $ASTROAI_LAB_BIN_DIR (scratch or team project, not $HOME).

    Examples:
        astroai-lab agent install claude
        astroai-lab agent install --list
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
            ui.print_hint("  astroai-lab agent models free")


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
        astroai-lab agent models free
        astroai-lab agent models free --preset long
        export OPENROUTER_API_KEY=sk-or-v1-... && astroai-lab agent models free
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
        ui.print_hint("  Full guide: `astroai-lab agent models`")
