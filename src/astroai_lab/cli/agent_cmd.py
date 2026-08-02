from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.agent import addons as agent_addons
from astroai_lab.agent import catalog as agent_catalog_mod
from astroai_lab.agent import clean_agent as agent_clean_mod
from astroai_lab.agent import fix as agent_fix_mod
from astroai_lab.agent import free_models as agent_free_models
from astroai_lab.agent import install as agent_install
from astroai_lab.agent import interact as agent_interact_mod
from astroai_lab.agent import inventory as agent_inventory
from astroai_lab.agent import setup as agent_setup_mod
from astroai_lab.agent import upstream as agent_upstream
from astroai_lab.cli.context import get_opts
from astroai_lab.core.paths import user_bin_dir
from astroai_lab.errors import LabError

agent_app = typer.Typer(
    help=(
        "AI coding agents: install CLIs, write configs/skills, verify, free models.\n\n"
        "Quick map:\n"
        "  catalog    curated catalog (agents + skills + MCPs + container UIs)\n"
        "  list       overview (tools + bundles + skills)\n"
        "  install    download a CLI binary (kilo, opencode, qoder, …)\n"
        "  remove     uninstall a CLI binary + config files\n"
        "  setup      write MCP/rules/skills configs\n"
        "  update     refresh configs + upstream skills\n"
        "  addons     curated skills/rules/MCP (lean + science)\n"
        "  add        install curated addon(s) by id or --tag\n"
        "  skills     Cursor skill inventory / refresh upstream\n"
        "  project    per-project AGENTS.md + .cursor scaffold\n"
        "  status     binaries + configs at a glance (--endpoints for container UIs)\n"
        "  verify     presence + config syntax checks (with --fix)\n"
        "  fix-config auto-repair setup state, locks, & config syntax\n"
        "  models     free-tier model presets\n"
        "Deprecated aliases: fix, clean, report, interact — see `astroai-lab help -c agent`"
    ),
)


@agent_app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("AI agents — pick one:")
        ui.print_hint(
            "  astroai-lab agent catalog           # curated AI tools & container catalog"
        )
        ui.print_hint("  astroai-lab agent list              # tools, bundles, skills overview")
        ui.print_hint("  astroai-lab agent install [TOOL]    # CLI binaries (omit TOOL to list)")
        ui.print_hint("  astroai-lab agent remove TOOL       # uninstall (--purge for home dirs)")
        ui.print_hint("  astroai-lab agent setup [BUNDLE…]   # MCP/rules/skills configs")
        ui.print_hint("  astroai-lab agent addons            # curated lean + science addons")
        ui.print_hint("  astroai-lab agent add ponytail      # install curated addon(s)")
        ui.print_hint("  astroai-lab agent skills list       # Cursor skills inventory")
        ui.print_hint(
            "  astroai-lab agent status|verify     # health check (or agent verify --fix)"
        )
        ui.print_hint(
            "  astroai-lab agent fix-config        # auto-repair (--clean for stale state)"
        )
        ui.print_hint("  astroai-lab agent models free       # OpenRouter / Kilo presets")
        ui.print_hint(
            "  (deprecated: fix, clean, report, interact → "
            "fix-config / status --json / status --endpoints)"
        )


# ---------------------------------------------------------------------------
# Shell-completion callables for option/argument values. Each matches typer's
# autocompletion signature (ctx, incomplete) -> list[str]; failures degrade to
# empty completions so tab-completion never crashes the CLI.
# ---------------------------------------------------------------------------


def _preset_completer(ctx, incomplete: str) -> list[str]:
    """Offer free-model preset names (`agent models free --preset`)."""
    return [n for n in agent_free_models.list_presets() if n.startswith(incomplete or "")]


def _tool_completer(ctx, incomplete: str) -> list[str]:
    """Offer installable CLI names (`agent install NAME`)."""
    incomplete = incomplete or ""
    try:
        names = [str(row["name"]) for row in agent_install.list_tools_status()]
        from astroai_lab.agent.registry import registry_ids

        names += sorted(registry_ids())
    except Exception:  # noqa: BLE001 — completion must never crash the CLI
        return []
    return sorted({n for n in names if n.startswith(incomplete)})


def _bundle_completer(ctx, incomplete: str) -> list[str]:
    """Offer config bundle names (`agent setup NAME`)."""
    incomplete = incomplete or ""
    try:
        names = list(agent_setup_mod.agent_list_bundles())
    except Exception:  # noqa: BLE001 — completion must never crash the CLI
        return []
    return [n for n in names if n.startswith(incomplete)]


def _addon_completer(ctx, incomplete: str) -> list[str]:
    """Offer curated addon ids (`agent add NAME`)."""
    incomplete = incomplete or ""
    try:
        ids = [row["id"] for row in agent_addons.list_addons()]
    except Exception:  # noqa: BLE001 — completion must never crash the CLI
        return []
    return [i for i in ids if i.startswith(incomplete)]


ADDON_KINDS = ("skill", "bundle", "mcp", "tool", "rule")
CATALOG_KINDS = ("agent", "skill", "rule", "mcp", "tool", "container")


def _addon_kind_completer(ctx, incomplete: str) -> list[str]:
    return [k for k in ADDON_KINDS if k.startswith(incomplete or "")]


def _catalog_kind_completer(ctx, incomplete: str) -> list[str]:
    return [k for k in CATALOG_KINDS if k.startswith(incomplete or "")]


@agent_app.command("setup")
def agent_setup_cmd(
    ctx: typer.Context,
    bundle: Annotated[list[str] | None, typer.Argument(autocompletion=_bundle_completer)] = None,
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
        ui.print_warn(f"Partial setup — {len(result.actions)} ok, {len(result.errors)} failed")
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


def _print_interact(opts) -> None:
    """Active container UI endpoints + agent CLI status (was `agent interact`)."""
    info = agent_interact_mod.inspect_interact_endpoints()
    if opts.json:
        ui.print_json(info)
        return
    ui.print_hint(f"Interactive Session Diagnostics ({info['session_kind'].upper()})")
    ui.print_hint(
        "  Active Agent CLIs: "
        + (", ".join(info["installed_agents"]) if info["installed_agents"] else "None")
    )
    ui.print_hint("")
    ui.print_hint("Endpoints & Access Points:")
    for ep in info["endpoints"]:
        mark = "✓ ONLINE" if ep["active"] else "— OFFLINE"
        ui.print_hint(f"  [{mark}] {ep['name']} ({ep['url_hint']})")
        ui.print_hint(f"          {ep['description']}")


@agent_app.command("status")
def agent_status_cmd(
    ctx: typer.Context,
    endpoints: Annotated[
        bool,
        typer.Option(
            "--endpoints",
            help="Show active container UI endpoints (was `agent interact`).",
        ),
    ] = False,
) -> None:
    """Show which agents are installed, configured, and have issues.

    `--endpoints` lists active container UI endpoints (the former `interact`
    surface, preserved verbatim).
    """
    from astroai_lab.agent.setup_state import build_agent_report, read_setup_state

    opts = get_opts(ctx)
    if endpoints:
        _print_interact(opts)
        return
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


def _installable_tools() -> list[dict]:
    """Full installable surface: legacy TOOLS + registry-driven agents.

    Shared by `agent install` and `agent list` so their JSON `tools` section
    stays consistent after the Phase 2 TOOLS->registry migration.
    """
    rows = agent_install.list_tools_status()
    from astroai_lab.agent.registry import list_registry_agents, registry_agent_status

    seen = {str(row["name"]) for row in rows}
    for agent in list_registry_agents():
        if agent["id"] in seen:
            continue
        status = registry_agent_status(agent)
        rows.append(
            {
                "name": agent["id"],
                "binary": agent["binary"],
                "description": agent.get("summary", ""),
                "installed": status["binary_ok"],
            }
        )
    return rows


def _print_tools(as_json: bool) -> None:
    rows = _installable_tools()
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Installable CLIs — install with: astroai-lab agent install NAME")
    ui.print_hint("  Name         Binary       On PATH   Description")
    ui.print_hint("  ───────────  ───────────  ────────  ───────────")
    for row in rows:
        mark = "✓" if row["installed"] else "—"
        ui.print_hint(f"  {row['name']:<12} {row['binary']:<12} {mark:<8} {row['description']}")


def _print_registry(rows: list[dict]) -> None:
    """Registered agents (YAML registry) with binary + config status."""
    if not rows:
        return
    ui.print_hint("Registered agents (YAML registry) — status: binary / config")
    ui.print_hint("  Agent        Binary    Config")
    ui.print_hint("  ─────────    ───────   ──────")
    for row in rows:
        b = "✓" if row["binary_ok"] else "✗"
        c = "✓" if row["config_ok"] else "—"
        ui.print_hint(f"  {row['name']:<12} {b:<9} {c}")
    ui.print_hint("  Install: astroai-lab agent install <id> · Verify: agent verify")


def _print_skills(as_json: bool, *, home: Path | None = None) -> None:
    rows = agent_inventory.list_skills_inventory(home)
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
        status = "default" if row["default"] else ("installed" if row["installed"] else "—")
        tags = ",".join(row["tags"]) if row["tags"] else ""
        ui.print_hint(f"  {row['id']:<32} {row['kind']:<8} {status:<9} {tags}")
        if row["summary"]:
            ui.print_hint(f"    {row['summary']}")


@agent_app.command("addons")
def agent_addons_cmd(
    ctx: typer.Context,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            "-k",
            help="Filter: skill, bundle, mcp, tool, rule.",
            autocompletion=_addon_kind_completer,
        ),
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
    names: Annotated[
        list[str] | None, typer.Argument(help="Addon id(s).", autocompletion=_addon_completer)
    ] = None,
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


def _update_github_skills(ctx: typer.Context) -> None:
    opts = get_opts(ctx)
    try:
        results = agent_upstream.update_all_github_sources(force=True, dry_run=opts.dry_run)
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
        raise typer.Exit(
            2 if failures < len([a for a in actions if a["status"] != "skipped"]) else 1
        )
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


@agent_app.command("catalog")
def agent_catalog_cmd(
    ctx: typer.Context,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            "-k",
            help="Filter: agent, skill, rule, mcp, tool, container.",
            autocompletion=_catalog_kind_completer,
        ),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option(
            "--tag", "-t", help="Filter tag: lean, science, python, review, open, ui, ..."
        ),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", "-s", help="Search text in catalog."),
    ] = None,
) -> None:
    """Curated Catalog & Directory of agents, skills, rules, MCP servers, tools & containers."""
    opts = get_opts(ctx)
    items = agent_catalog_mod.list_agent_catalog(kind=kind, tag=tag, query=search)
    if opts.json:
        ui.print_json(items)
        return
    ui.print_hint("AstroAI Agent & Container Catalog (Agents, Skills, Rules, MCPs, UIs)")
    ui.print_hint("  Id                               Kind       Status     Summary")
    ui.print_hint(
        "  ───────────────────────────────  ─────────  ─────────  ──────────────────────────"
    )
    for item in items:
        status = "installed" if item["installed"] else "available"
        ui.print_hint(f"  {item['id']:<32} {item['kind']:<10} {status:<10} {item['summary']}")
        if item.get("install_command"):
            ui.print_hint(f"    > {item['install_command']}")


@agent_app.command("fix-config")
def agent_fix_config_cmd(
    ctx: typer.Context,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Clean stale state instead of auto-repairing."),
    ] = False,
    stale_locks: Annotated[
        bool, typer.Option("--stale-locks", help="Remove stale lock files.")
    ] = True,
    failed: Annotated[bool, typer.Option("--failed", help="Clear failed setup marker.")] = True,
    empty_configs: Annotated[
        bool, typer.Option("--empty-configs", help="Remove empty config files.")
    ] = True,
    logs: Annotated[bool, typer.Option("--logs", help="Remove setup log file.")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Auto-repair agent setup (or `--clean` stale state). Replaces `fix` + `clean`.

    Examples:
        astroai-lab agent fix-config
        astroai-lab agent fix-config --clean
        astroai-lab agent fix-config --clean --logs
    """
    from astroai_lab.cli.context import merge_opts

    opts = merge_opts(ctx, dry_run=dry_run)
    if clean:
        results = agent_clean_mod.clean_agent_state(
            stale_locks=stale_locks,
            failed_marker=failed,
            empty_configs=empty_configs,
            logs=logs,
            dry_run=opts.dry_run,
        )
        if opts.json:
            ui.print_json([r.__dict__ for r in results])
            return
        if not results:
            ui.print_ok("Agent state clean — no stale locks or broken markers found")
            return
        for r in results:
            prefix = "would remove" if opts.dry_run else "removed"
            ui.print_ok(f"  {r.target}: {prefix} ({r.detail})")
        return

    results = agent_fix_mod.fix_agent_setup(dry_run=opts.dry_run)
    if opts.json:
        ui.print_json([r.__dict__ for r in results])
        return
    fixed_count = sum(1 for r in results if r.fixed)
    prefix = "would fix" if opts.dry_run else "repaired"
    for r in results:
        if r.fixed:
            ui.print_ok(f"  {r.target}: {prefix} — {r.detail}")
        else:
            ui.print_warn(f"  {r.target}: {r.detail}")
    if fixed_count:
        ui.print_ok(f"Agent setup fix complete ({fixed_count} item(s) {prefix})")
    else:
        ui.print_ok("Agent setup already healthy")


def _deprecated_alias(old: str, new: str) -> None:
    """Emit a deprecation hint to stderr (keeps stdout JSON-clean)."""
    ui.print_warn(f"`agent {old}` is deprecated — use `agent {new}`")


@agent_app.command("fix", hidden=True)
def agent_fix_cmd(
    ctx: typer.Context,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Deprecated: use `agent fix-config`."""
    _deprecated_alias("fix", "fix-config")
    agent_fix_config_cmd(ctx, clean=False, dry_run=dry_run)


@agent_app.command("clean", hidden=True)
def agent_clean_cmd(
    ctx: typer.Context,
    stale_locks: Annotated[
        bool, typer.Option("--stale-locks", help="Remove stale lock files.")
    ] = True,
    failed: Annotated[bool, typer.Option("--failed", help="Clear failed setup marker.")] = True,
    empty_configs: Annotated[
        bool, typer.Option("--empty-configs", help="Remove empty config files.")
    ] = True,
    logs: Annotated[bool, typer.Option("--logs", help="Remove setup log file.")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Deprecated: use `agent fix-config --clean`."""
    _deprecated_alias("clean", "fix-config --clean")
    agent_fix_config_cmd(
        ctx,
        clean=True,
        stale_locks=stale_locks,
        failed=failed,
        empty_configs=empty_configs,
        logs=logs,
        dry_run=dry_run,
    )


@agent_app.command("interact", hidden=True)
def agent_interact_cmd(ctx: typer.Context) -> None:
    """Deprecated: use `agent status --endpoints`."""
    _deprecated_alias("interact", "status --endpoints")
    _print_interact(get_opts(ctx))


@agent_app.command("verify")
def agent_verify_cmd(
    ctx: typer.Context,
    auto_fix: Annotated[
        bool,
        typer.Option(
            "--fix", "-f", help="Auto-repair missing directories, stale locks, or syntax errors."
        ),
    ] = False,
) -> None:
    """Check agent setup: required files plus JSON/TOML/YAML syntax of configs.

    Catches common OpenCode/Kilo JSONC mistakes (comments, trailing commas,
    broken braces) without needing to launch the agent.
    """
    from astroai_lab.agent.setup_state import read_setup_state

    opts = get_opts(ctx)
    home = Path.home()

    if auto_fix:
        agent_fix_mod.fix_agent_setup(dry_run=opts.dry_run)

    issues = agent_inventory.verify_setup(home)
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
        ui.print_hint(
            "Tip: Run `astroai-lab agent fix-config` "
            "or `astroai-lab agent verify --fix` to auto-repair."
        )
        raise typer.Exit(1)
    if state.stamp:
        ui.print_hint(f"  last run: {state.stamp}")
    ui.print_ok("Agent setup OK")


@agent_app.command("report", hidden=True)
def agent_report_cmd(ctx: typer.Context) -> None:
    """Deprecated: use `agent status --json`."""
    _deprecated_alias("report", "status --json")
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
    from astroai_lab.agent.registry import list_registry_agents, registry_agent_status

    registry_rows = [registry_agent_status(a) for a in list_registry_agents()]
    if opts.json:
        ui.print_json(
            {
                "tools": _installable_tools(),
                "registry": registry_rows,
                "bundles": agent_setup_mod.agent_list_bundles(),
                "skills": agent_inventory.list_skills_inventory(),
                "addons": agent_addons.list_addons(),
            }
        )
        return
    _print_tools(False)
    ui.print_hint("")
    _print_registry(registry_rows)
    ui.print_hint("")
    _print_bundles(False)
    ui.print_hint("")
    _print_skills(False)
    ui.print_hint("")
    ui.print_hint("Curated addons: `astroai-lab agent addons` · `astroai-lab agent add NAME`")


@agent_app.command("install")
def agent_install_cmd(
    ctx: typer.Context,
    tool: Annotated[
        str | None,
        typer.Argument(help="Tool name (omit to list).", autocompletion=_tool_completer),
    ] = None,
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
        from astroai_lab.agent.registry import get_registry_agent, install_registry_agent

        if tool in agent_install.TOOLS:
            agent_install.install_tool(tool, dry_run=opts.dry_run)
        elif get_registry_agent(tool) is not None:
            install_registry_agent(tool, dry_run=opts.dry_run)
        else:
            raise LabError(
                f"Unknown tool: {tool}", hint="astroai-lab agent list  (or agent catalog)"
            )
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


@agent_app.command("remove")
def agent_remove_cmd(
    ctx: typer.Context,
    tool: Annotated[
        str,
        typer.Argument(help="Tool/agent name (omit to list).", autocompletion=_tool_completer),
    ],
    purge: Annotated[
        bool,
        typer.Option("--purge", help="Also remove the agent's home dir (~/.hermes, ~/.openclaw)."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Uninstall an agent CLI: binary, config files, plugin files, setup stamps.

    ``--purge`` additionally removes the agent's whole home config dir (e.g.
    ``~/.hermes``, ``~/.openclaw``). Dry-run lists what would be removed.

    Examples:
        astroai-lab agent remove kilo
        astroai-lab agent remove hermes --purge
        astroai-lab agent remove openclaw --dry-run
    """
    from astroai_lab.agent.registry import remove_registry_agent
    from astroai_lab.cli.context import merge_opts

    opts = merge_opts(ctx, dry_run=dry_run)
    try:
        if tool in agent_install.TOOLS:
            results = [
                r.__dict__
                for r in agent_install.uninstall_tool(tool, purge=purge, dry_run=opts.dry_run)
            ]
        else:
            results = remove_registry_agent(tool, purge=purge, dry_run=opts.dry_run)
    except LabError as exc:
        if opts.json:
            ui.print_json(
                {
                    "ok": False,
                    "tool": tool,
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
                "tool": tool,
                "purge": purge,
                "dry_run": opts.dry_run,
                "actions": results,
                "errors": [],
            }
        )
        return
    if not results:
        ui.print_ok(f"{tool}: nothing to remove")
        return
    prefix = "would remove" if opts.dry_run else "removed"
    for r in results:
        status = r["status"]
        if status == "error":
            ui.print_error(f"  {r['target']}: {r['detail']}")
        elif status == "would_remove":
            ui.print_hint(f"  {r['target']}: {prefix} ({r['detail']})")
        else:
            ui.print_ok(f"  {r['target']}: {prefix} ({r['detail']})")


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
    preset: Annotated[
        str,
        typer.Option("--preset", "-p", help="Preset name.", autocompletion=_preset_completer),
    ] = "coding",
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
