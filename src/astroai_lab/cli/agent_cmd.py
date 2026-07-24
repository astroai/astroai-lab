from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.agent import addons as agent_addons
from astroai_lab.agent import bundles as agent_setup_mod
from astroai_lab.agent import free_models as agent_free_models
from astroai_lab.agent import install as agent_install
from astroai_lab.cli.context import get_opts
from astroai_lab.core.paths import user_bin_dir
from astroai_lab.errors import LabError

agent_app = typer.Typer(
    help=(
        "AI coding agents: install CLIs, write configs/skills, verify, free models.\n\n"
        "Quick map:\n"
        "  list       overview (tools + bundles + skills)\n"
        "  install    download a CLI binary (kilo, opencode, qoder, …)\n"
        "  setup      write MCP/rules/skills configs\n"
        "  addons     curated skills/rules/MCP (lean + science) — not a list of agents\n"
        "  add        install curated addon(s) by id or --tag\n"
        "  skills     Cursor skill inventory / refresh upstream\n"
        "  status     binaries + configs at a glance\n"
        "  verify     presence + config syntax checks\n"
        "  report     one-shot JSON health (wizard)\n"
        "  models     free-tier model presets"
    ),
)


@agent_app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("AI agents — pick one:")
        ui.print_hint("  astroai-lab agent list              # tools, bundles, skills overview")
        ui.print_hint("  astroai-lab agent install [TOOL]    # CLI binaries (omit TOOL to list)")
        ui.print_hint("  astroai-lab agent setup [BUNDLE…]   # MCP/rules/skills configs")
        ui.print_hint("  astroai-lab agent addons            # curated lean + science addons")
        ui.print_hint("  astroai-lab agent add ponytail      # install curated addon(s)")
        ui.print_hint("  astroai-lab agent skills list       # Cursor skills inventory")
        ui.print_hint("  astroai-lab agent status|verify     # health check")
        ui.print_hint("  astroai-lab agent models free       # OpenRouter / Kilo presets")


@agent_app.command("setup")
def agent_setup_cmd(
    ctx: typer.Context,
    bundle: Annotated[list[str] | None, typer.Argument()] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
    list_bundles: Annotated[
        bool,
        typer.Option("--list", "-l", help="List config bundles (not installable CLIs)."),
    ] = False,
) -> None:
    """Write MCP, rules, and skills configs for AI coding agents.

    Examples:
        astroai-lab agent setup
        astroai-lab agent setup cursor claude
        astroai-lab agent setup --list
        astroai-lab --json agent setup
    """
    if list_bundles:
        _print_bundles(get_opts(ctx).json)
        return
    opts = get_opts(ctx)
    try:
        result = agent_setup_mod.agent_setup(
            mode="install",
            bundles=list(bundle) if bundle else None,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        if opts.json:
            ui.print_json(
                {
                    "ok": False,
                    "partial": False,
                    "mode": "install",
                    "actions": [],
                    "errors": [str(exc)],
                    "warnings": [],
                    "stamp": None,
                }
            )
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc

    if opts.json:
        ui.print_json(result.to_dict())
        if result.exit_code:
            raise typer.Exit(result.exit_code)
        return

    for w in result.warnings:
        ui.print_warn(w)
    for err in result.errors:
        ui.print_error(err)
    if result.ok and not result.partial:
        ui.print_ok("Agent setup complete")
    elif result.partial:
        ui.print_warn(
            f"Partial setup — {len(result.actions)} ok, {len(result.errors)} failed"
        )
    else:
        ui.print_error("Agent setup failed")
    ui.print_hint("  astroai-lab agent install kilo|goose|cline|qoder|opencode")
    ui.print_hint("  astroai-lab agent addons            # curated lean + science addons")
    ui.print_hint("  astroai-lab agent add ponytail      # YAGNI / minimal diffs")
    ui.print_hint("  astroai-lab agent models free")
    ui.print_hint("  astroai-lab init myproject")
    if result.exit_code:
        raise typer.Exit(result.exit_code)


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
    from astroai_lab.agent.setup_state import build_agent_report, read_setup_state

    opts = get_opts(ctx)
    home = Path.home()
    report = build_agent_report(home)
    if opts.json:
        ui.print_json(report)
        return
    ui.print_hint("  Agent        Binary    Config")
    ui.print_hint("  ─────────    ───────   ──────")
    for row in report["agents"]:
        b = "✓" if row["binary"] else "✗"
        c = "✓" if row["config"] else "—"
        ui.print_hint(f"  {row['agent']:<12} {b:<9} {c}")
    issues = report["issues"]
    if issues:
        ui.print_hint("")
        for issue in issues:
            ui.print_warn(f"  {issue}")
    state = read_setup_state(home)
    if state.stamp:
        ui.print_hint("")
        ui.print_hint(f"  Last setup: {state.stamp}")
    if state.failed:
        ui.print_warn(f"  Last failure: {state.failed}")


def _run_agent_sync(ctx: typer.Context) -> None:
    opts = get_opts(ctx)
    try:
        results = agent_setup_mod.agent_sync(dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    failures = [r for r in results if r.status == "failed"]
    verify_failed = False
    if not opts.dry_run:
        try:
            agent_setup_mod.agent_verify()
        except LabError as exc:
            verify_failed = True
            ui.print_warn(str(exc))
            from astroai_lab.agent.setup_state import record_setup_failed

            record_setup_failed(exit_code=2, detail=str(exc)[:500])
    prefix = "would refresh" if opts.dry_run else "refreshed"
    for result in results:
        if result.status == "skipped":
            continue
        if result.status == "failed":
            ui.print_error(f"{result.name}: {result.detail}")
        else:
            ui.print_ok(f"{prefix} skill {result.name} ({result.repo}: {result.status})")
    if failures or verify_failed:
        ui.print_warn("Agent config update finished with issues")
        raise typer.Exit(2)
    ui.print_ok("Agent config updated")


def _print_bundles(as_json: bool) -> None:
    rows = agent_setup_mod.agent_list_bundles()
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Config bundles — apply with: astroai-lab agent setup [NAME…]")
    for name, desc in rows.items():
        ui.print_hint(f"  {name:<14} {desc}")


def _print_tools(as_json: bool) -> None:
    rows = agent_install.list_tools_status()
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Installable CLIs — install with: astroai-lab agent install NAME")
    ui.print_hint("  Name         Binary       On PATH   Description")
    ui.print_hint("  ───────────  ───────────  ────────  ───────────")
    for row in rows:
        mark = "✓" if row["installed"] else "—"
        ui.print_hint(
            f"  {row['name']:<12} {row['binary']:<12} {mark:<8} {row['description']}"
        )


def _print_skills(as_json: bool, *, home: Path | None = None) -> None:
    rows = agent_setup_mod.list_skills_inventory(home)
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Cursor skills (~/.cursor/skills) — refresh: astroai-lab agent skills update")
    ui.print_hint("  Name                             Source        Status")
    ui.print_hint("  ───────────────────────────────  ────────────  ──────────")
    for row in rows:
        if row["source"] == "pixi-skills":
            status = "pixi-only"
        else:
            status = "installed" if row["installed"] else "missing"
        detail = row["repo"] or row.get("note") or ""
        line = f"  {row['name']:<32} {row['source']:<13} {status}"
        ui.print_hint(line)
        if detail:
            ui.print_hint(f"    {detail}")


def _print_addons(
    as_json: bool,
    *,
    kind: str | None = None,
    tag: str | None = None,
) -> None:
    rows = agent_addons.list_addons(kind=kind, tag=tag)
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint(
        "Curated addons (skills/rules/MCP/tools) — not a list of agents. "
        "Install: astroai-lab agent add NAME"
    )
    ui.print_hint("  Id                               Kind     Status     Tags / summary")
    ui.print_hint("  ───────────────────────────────  ───────  ─────────  ──────────────")
    for row in rows:
        status = (
            "default" if row["default"] else ("installed" if row["installed"] else "—")
        )
        tags = ",".join(row["tags"]) if row["tags"] else ""
        ui.print_hint(
            f"  {row['id']:<32} {row['kind']:<8} {status:<9} {tags}"
        )
        if row["summary"]:
            ui.print_hint(f"    {row['summary']}")


@agent_app.command("addons")
def agent_addons_cmd(
    ctx: typer.Context,
    kind: Annotated[
        str | None,
        typer.Option("--kind", "-k", help="Filter: skill, bundle, mcp, tool, rule."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Filter tag: lean, science, python, review, …"),
    ] = None,
) -> None:
    """List curated lean-coding and science addons (not a catalog of agents).

    Examples:
        astroai-lab agent addons
        astroai-lab agent addons --tag lean
        astroai-lab agent addons --kind skill
    """
    _print_addons(get_opts(ctx).json, kind=kind, tag=tag)


@agent_app.command("add")
def agent_add_cmd(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(help="Addon id(s).")] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Install all addons with this tag (skips defaults)."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Install curated addon(s) by id or tag.

    Examples:
        astroai-lab agent add ponytail
        astroai-lab agent add ponytail polars modern-python
        astroai-lab agent add --tag lean
        astroai-lab agent add --dry-run git-mcp
    """
    opts = get_opts(ctx)
    try:
        results = agent_addons.add_addons(
            list(names) if names else None,
            tag=tag,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    failures = 0
    actions: list[dict[str, str]] = []
    for result in results:
        actions.append({"id": result.id, "status": result.status, "detail": result.detail})
        if result.status == "failed":
            failures += 1
            if not opts.json:
                ui.print_error(f"{result.id}: {result.detail}")
        elif opts.json:
            continue
        elif result.status == "skipped":
            ui.print_hint(f"  skip {result.id}: {result.detail}")
        elif result.status == "dry-run":
            ui.print_ok(f"would add {result.id} ({result.detail})")
        else:
            ui.print_ok(f"added {result.id} ({result.status}: {result.detail})")
    if opts.json:
        ok = failures == 0
        partial = failures > 0 and failures < len(results)
        ui.print_json(
            {
                "ok": ok,
                "partial": partial,
                "actions": actions,
                "errors": [a["detail"] for a in actions if a["status"] == "failed"],
                "warnings": [],
            }
        )
        if failures and partial:
            raise typer.Exit(2)
        if failures:
            raise typer.Exit(1)
        return
    if failures:
        raise typer.Exit(1 if failures == len(results) else 2)


skills_app = typer.Typer(help="Cursor skills: inventory and GitHub upstream refresh.")
agent_app.add_typer(skills_app, name="skills")


@skills_app.callback(invoke_without_command=True)
def skills_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _print_skills(get_opts(ctx).json)


@skills_app.command("list")
def skills_list_cmd(ctx: typer.Context) -> None:
    """List bundled, GitHub, pixi-only, and extra Cursor skills."""
    _print_skills(get_opts(ctx).json)


@skills_app.command("update")
def skills_update_cmd(ctx: typer.Context) -> None:
    """Pull GitHub upstream skill sources and refresh ~/.cursor/skills copies.

    Examples:
        astroai-lab agent skills update
        astroai-lab agent skills update --dry-run
    """
    _update_github_skills(ctx)


# Keep `sources` as a thin alias so older docs/scripts keep working.
sources_app = typer.Typer(
    help="Alias for `agent skills` (GitHub upstream skill sources).",
    hidden=False,
)
agent_app.add_typer(sources_app, name="sources")


@sources_app.callback(invoke_without_command=True)
def sources_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("Prefer: `astroai-lab agent skills list` | `astroai-lab agent skills update`")
        ui.print_hint("(sources is an alias for skills)")


@sources_app.command("list")
def sources_list_cmd(ctx: typer.Context) -> None:
    """List skill sources (alias for ``agent skills list``)."""
    _print_skills(get_opts(ctx).json)


@sources_app.command("update")
def sources_update_cmd(ctx: typer.Context) -> None:
    """Pull GitHub upstream skills (alias for ``agent skills update``)."""
    _update_github_skills(ctx)


def _update_github_skills(ctx: typer.Context) -> None:
    opts = get_opts(ctx)
    try:
        results = agent_setup_mod.update_all_github_sources(force=True, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    prefix = "would update" if opts.dry_run else "updated"
    failures = 0
    actions = []
    for result in results:
        actions.append(
            {
                "name": result.name,
                "repo": result.repo,
                "status": result.status,
                "detail": result.detail,
            }
        )
        if result.status == "failed":
            failures += 1
            if not opts.json:
                ui.print_error(f"{result.name}: {result.detail}")
        elif result.status != "skipped" and not opts.json:
            ui.print_ok(f"{prefix} {result.name} ({result.repo}: {result.status})")
    if opts.json:
        ok = failures == 0
        partial = failures > 0 and any(a["status"] != "failed" for a in actions)
        ui.print_json(
            {
                "ok": ok,
                "partial": partial,
                "actions": actions,
                "errors": [a["detail"] for a in actions if a["status"] == "failed"],
            }
        )
        if failures and partial:
            raise typer.Exit(2)
        if failures:
            raise typer.Exit(1)
        return
    if failures:
        raise typer.Exit(2 if failures < len([a for a in actions if a["status"] != "skipped"]) else 1)
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
        result = agent_setup_mod.agent_setup(
            mode="project",
            project_dir=project.resolve(),
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        if opts.json:
            ui.print_json(
                {
                    "ok": False,
                    "partial": False,
                    "mode": "project",
                    "actions": [],
                    "errors": [str(exc)],
                    "warnings": [],
                    "stamp": None,
                }
            )
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(result.to_dict())
        if result.exit_code:
            raise typer.Exit(result.exit_code)
        return
    if result.ok:
        ui.print_ok(f"Project templates installed in {project}")
    else:
        for err in result.errors:
            ui.print_error(err)
        raise typer.Exit(result.exit_code)


@agent_app.command("verify")
def agent_verify_cmd(ctx: typer.Context) -> None:
    """Check agent setup: required files plus JSON/TOML/YAML syntax of configs.

    Catches common OpenCode/Kilo JSONC mistakes (comments, trailing commas,
    broken braces) without needing to launch the agent.
    """
    from astroai_lab.agent.setup_state import read_setup_state

    opts = get_opts(ctx)
    home = Path.home()
    issues = agent_setup_mod.verify_setup(home)
    state = read_setup_state(home)
    payload = {
        "ok": not issues,
        "issues": issues,
        "setup": state.to_dict(),
    }
    if opts.json:
        ui.print_json(payload)
        if issues:
            raise typer.Exit(1)
        return
    if issues:
        ui.print_error("Agent setup incomplete:\n  " + "\n  ".join(issues))
        raise typer.Exit(1)
    if state.stamp:
        ui.print_hint(f"  last run: {state.stamp}")
    ui.print_ok("Agent setup OK")


@agent_app.command("report")
def agent_report_cmd(ctx: typer.Context) -> None:
    """One-shot JSON report: stamp, failed marker, verify issues, binaries.

    Intended for the agent wizard / automation (always JSON).
    """
    from astroai_lab.agent.setup_state import build_agent_report

    report = build_agent_report()
    ui.print_json(report)
    if not report.get("ok"):
        raise typer.Exit(1)


@agent_app.command("list")
def agent_list_cmd(ctx: typer.Context) -> None:
    """Overview of installable CLIs, config bundles, and Cursor skills.

    Prefer this over guessing between ``install`` / ``setup`` / ``skills``.
    Curated lean/science recommendations: ``agent addons``.
    """
    opts = get_opts(ctx)
    if opts.json:
        ui.print_json(
            {
                "tools": agent_install.list_tools_status(),
                "bundles": agent_setup_mod.agent_list_bundles(),
                "skills": agent_setup_mod.list_skills_inventory(),
                "addons": agent_addons.list_addons(),
            }
        )
        return
    _print_tools(False)
    ui.print_hint("")
    _print_bundles(False)
    ui.print_hint("")
    _print_skills(False)
    ui.print_hint("")
    ui.print_hint(
        "Curated addons: `astroai-lab agent addons` · `astroai-lab agent add NAME`"
    )


@agent_app.command("install")
def agent_install_cmd(
    ctx: typer.Context,
    tool: Annotated[str | None, typer.Argument(help="Tool name (omit to list).")] = None,
    list_tools: Annotated[
        bool,
        typer.Option("--list", "-l", help="List installable CLIs (same as omitting TOOL)."),
    ] = False,
) -> None:
    """Install AI coding CLIs to $ASTROAI_LAB_BIN_DIR (scratch/team, not $HOME).

    Examples:
        astroai-lab agent install              # list CLIs
        astroai-lab agent install kilo
        astroai-lab agent install qoder
        astroai-lab agent install --list
    """
    opts = get_opts(ctx)
    if list_tools or not tool:
        _print_tools(opts.json)
        if not tool and not list_tools:
            ui.print_hint("")
            ui.print_hint("Install one with: astroai-lab agent install NAME")
        return
    try:
        agent_install.install_tool(tool, dry_run=opts.dry_run)
    except LabError as exc:
        if opts.json:
            ui.print_json(
                {
                    "ok": False,
                    "tool": tool,
                    "actions": [],
                    "errors": [str(exc)],
                    "warnings": [],
                }
            )
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": True,
                "tool": tool,
                "actions": [f"install:{tool}"],
                "errors": [],
                "warnings": [],
                "bin_dir": str(user_bin_dir()) if not opts.dry_run else None,
                "dry_run": opts.dry_run,
            }
        )
        return
    if opts.dry_run:
        ui.print_ok(f"dry-run: would install {tool}")
    else:
        ui.print_ok(f"Installed {tool} → {user_bin_dir()}")
        if tool in ("kilo", "goose", "cline", "opencode", "codex", "qoder"):
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
        if opts.json:
            ui.print_json(
                {
                    "ok": False,
                    "preset": preset,
                    "actions": [],
                    "errors": [str(exc)],
                }
            )
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": True,
                "preset": preset,
                "actions": actions,
                "errors": [],
                "dry_run": opts.dry_run,
            }
        )
        return
    prefix = "would apply" if opts.dry_run else "applied"
    for line in actions:
        ui.print_ok(f"{prefix}: {line}")
    if not opts.dry_run:
        ui.print_hint("  Kilo sign-in: `kilo auth`  (or `/connect` in TUI)")
        ui.print_hint("  OpenRouter key: https://openrouter.ai/keys")
        ui.print_hint("  Full guide: `astroai-lab agent models`")
