"""Lean `astroai-lab agent` CLI surface.

Canonical verbs: list, install, remove, wipe, setup, config, update,
status, verify, repair, models, plugins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from astroai_lab import ui
from astroai_lab.agent import clean_agent as agent_clean_mod
from astroai_lab.agent import fix as agent_fix_mod
from astroai_lab.agent import free_models as agent_free_models
from astroai_lab.agent import install as agent_install
from astroai_lab.agent import interact as agent_interact_mod
from astroai_lab.agent import plugins as agent_plugins
from astroai_lab.agent import setup as agent_setup_mod
from astroai_lab.cli.context import get_opts
from astroai_lab.core.paths import user_bin_dir
from astroai_lab.errors import LabError

agent_app = typer.Typer(
    help=(
        "AI coding agents: install CLIs, configs, plugins, free models.\n\n"
        "Quick map:\n"
        "  list          registered agents (binary / config / version)\n"
        "  list config   skills/MCP/addons (plugins catalog)\n"
        "  install       download a CLI binary\n"
        "  setup         write MCP/rules/skills (--project for repo scaffold)\n"
        "  status        same as list (+ --ui for container endpoints)\n"
        "  verify|repair health check / auto-repair\n"
        "  models free   OpenRouter / Kilo presets\n"
        "  plugins       install/update/remove/configure plugins"
    ),
)


@agent_app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ui.print_hint("AI agents — pick one:")
        ui.print_hint("  astroai-lab agent list              # agents")
        ui.print_hint("  astroai-lab agent list config       # skills/MCP/addons")
        ui.print_hint("  astroai-lab agent install [NAME]    # omit NAME to list")
        ui.print_hint("  astroai-lab agent setup             # MCP/rules/skills")
        ui.print_hint("  astroai-lab agent models free")
        ui.print_hint("  astroai-lab agent verify|repair")


# ---------------------------------------------------------------------------
# Shell-completion callables
# ---------------------------------------------------------------------------


def _preset_completer(ctx, incomplete: str) -> list[str]:
    return [n for n in agent_free_models.list_presets() if n.startswith(incomplete or "")]


def _tool_completer(ctx, incomplete: str) -> list[str]:
    incomplete = incomplete or ""
    try:
        names = [str(row["name"]) for row in agent_install.list_tools_status()]
        from astroai_lab.agent.registry import registry_ids

        names += sorted(registry_ids())
    except Exception:  # noqa: BLE001 — completion must never crash the CLI
        return []
    return sorted({n for n in names if n.startswith(incomplete)})


def _bundle_completer(ctx, incomplete: str) -> list[str]:
    incomplete = incomplete or ""
    try:
        names = list(agent_setup_mod.agent_list_bundles())
        from astroai_lab.agent.registry import registry_ids

        names += sorted(registry_ids())
    except Exception:  # noqa: BLE001
        return []
    return [n for n in names if n.startswith(incomplete)]


def _agent_completer(ctx, incomplete: str) -> list[str]:
    incomplete = incomplete or ""
    try:
        from astroai_lab.agent.registry import registry_ids

        names = sorted(registry_ids())
    except Exception:  # noqa: BLE001
        return []
    return [n for n in names if n.startswith(incomplete)]


def _plugin_completer(ctx, incomplete: str) -> list[str]:
    incomplete = incomplete or ""
    try:
        ids = sorted(agent_plugins.plugin_ids())
    except Exception:  # noqa: BLE001
        return []
    return [i for i in ids if i.startswith(incomplete)]


def _plugin_kind_completer(ctx, incomplete: str) -> list[str]:
    return [k for k in agent_plugins.PLUGIN_KINDS if k.startswith(incomplete or "")]


# ---------------------------------------------------------------------------
# Shared printers
# ---------------------------------------------------------------------------


def _print_interact(opts) -> None:
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


def _print_status_table(
    report: dict, *, stamp: str | None = None, failed: str | None = None
) -> None:
    ui.print_hint("  Agent        Binary  Config  Version")
    ui.print_hint("  ───────────  ──────  ──────  ──────────")
    for row in report["agents"]:
        b = "✓" if row.get("binary_ok", row.get("binary")) else "—"
        if row.get("config_declared") is False:
            c = "·"  # no config path in registry
        else:
            c = "✓" if row.get("config_ok", row.get("config")) else "—"
        ver = row.get("version") or "—"
        name = row.get("id") or row.get("agent") or "?"
        ui.print_hint(f"  {name:<12} {b:<6} {c:<6} {ver}")
    issues = report.get("issues") or []
    if issues:
        ui.print_hint("")
        for issue in issues:
            ui.print_warn(f"  {issue}")
    if stamp:
        ui.print_hint("")
        ui.print_hint(f"  Last setup: {stamp}")
    if failed:
        ui.print_warn(f"  Last failure: {failed}")
    ui.print_hint("")
    ui.print_hint("  Install: astroai-lab agent install NAME")
    ui.print_hint("  Configs: astroai-lab agent list config")


def _print_bundles(as_json: bool) -> None:
    rows = agent_setup_mod.agent_list_bundles()
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Config bundles — apply with: astroai-lab agent setup [NAME…]")
    ui.print_hint("  (repo scaffold is `agent setup --project [DIR]`, not the `project` bundle)")
    for name, desc in rows.items():
        ui.print_hint(f"  {name:<14} {desc}")


def _installable_agents() -> list[dict]:
    """Registry agents only (install listing — no utilities)."""
    from astroai_lab.agent.registry import list_registry_agents, registry_agent_status

    rows: list[dict] = []
    for agent in list_registry_agents():
        status = registry_agent_status(agent, probe_ver=False)
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
    rows = _installable_agents()
    if as_json:
        ui.print_json(rows)
        return
    ui.print_hint("Installable agents — install with: astroai-lab agent install NAME")
    ui.print_hint("  Name         Binary       On PATH   Description")
    ui.print_hint("  ───────────  ───────────  ────────  ───────────")
    for row in rows:
        mark = "✓" if row["installed"] else "—"
        ui.print_hint(f"  {row['name']:<12} {row['binary']:<12} {mark:<8} {row['description']}")


def _print_config_plugins(
    as_json: bool,
    *,
    kind: str | None = None,
) -> None:
    rows = agent_plugins.list_plugins(kind=kind)
    if as_json:
        ui.print_json(rows)
        return
    if not rows:
        ui.print_hint("Configs: none in the plugin registry")
        return
    ui.print_hint("Configs (skills/MCP/addons) — install: astroai-lab agent plugins install ID")
    ui.print_hint("  Id                               Kind     Applied  Summary")
    ui.print_hint("  ───────────────────────────────  ───────  ───────  ────────")
    for row in rows:
        applied = "✓" if row["any_installed"] else "—"
        summary = (row.get("summary") or "")[:48]
        ui.print_hint(f"  {row['id']:<32} {row['kind']:<8} {applied:<7} {summary}")


def _print_plugins(
    as_json: bool,
    *,
    kind: str | None = None,
    agent: str | None = None,
) -> None:
    rows = agent_plugins.list_plugins(kind=kind, agent=agent)
    if as_json:
        ui.print_json(rows)
        return
    if not rows:
        ui.print_hint("Plugins: none in the registry (data/agent/plugins/*.yaml)")
        return
    ui.print_hint("Plugins (skills/MCP/config) — apply: astroai-lab agent plugins install ID")
    ui.print_hint("  Id          Kind     Status   Agents")
    ui.print_hint("  ──────────  ───────  ───────  ──────────────")
    for row in rows:
        status = "installed" if row["any_installed"] else "—"
        agents = ",".join(a for a in row["agents"] if row["installed"].get(a)) or row["agents"][0]
        ui.print_hint(f"  {row['id']:<11} {row['kind']:<8} {status:<7} {agents}")
        if row["summary"]:
            ui.print_hint(f"    {row['summary']}")


def _print_plugin_results(results, *, verb: str, dry_run: bool) -> None:
    failures = [r for r in results if r.status == "failed"]
    for r in results:
        scope = r.agent or "all"
        prefix = "would" if dry_run else ""
        if r.status == "failed":
            ui.print_error(f"{r.plugin}: {r.detail}")
        elif r.status in ("would_install", "would_remove"):
            ui.print_ok(f"{prefix} {r.plugin} ({scope}): {r.status} — {r.detail}")
        elif r.status in ("installed", "removed"):
            ui.print_ok(f"{r.plugin} ({scope}): {r.status} — {r.detail}")
        elif r.status == "skipped":
            ui.print_hint(f"{r.plugin} ({scope}): skip — {r.detail}")
        elif r.status == "no-op":
            ui.print_hint(f"{r.plugin} ({scope}): {r.detail}")
        else:
            ui.print_hint(f"{r.plugin} ({scope}): {r.status} — {r.detail}")
    if failures:
        raise typer.Exit(1)
    ui.print_ok(f"{verb} complete")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# list (agents) / list config (plugins)
# ---------------------------------------------------------------------------

list_app = typer.Typer(
    help="List registered agents (default) or configs (`list config`).",
    invoke_without_command=True,
)
agent_app.add_typer(list_app, name="list")


def _emit_agent_list(ctx: typer.Context) -> None:
    from astroai_lab.agent.setup_state import build_agent_report, read_setup_state

    opts = get_opts(ctx)
    home = Path.home()
    # Version probes are off by default in JSON/automation; human list opts in
    # unless ASTROAI_LAB_PROBE_VERSION=0 (tests set this).
    import os

    want_probe = (not opts.json) and os.environ.get("ASTROAI_LAB_PROBE_VERSION", "1") not in (
        "0",
        "false",
        "no",
    )
    report = build_agent_report(home, probe_ver=want_probe)
    state = read_setup_state(home)
    if opts.json:
        ui.print_json(report)
        if not report.get("ok"):
            raise typer.Exit(1)
        return
    _print_status_table(report, stamp=state.stamp, failed=state.failed)


@list_app.callback(invoke_without_command=True)
def list_root(ctx: typer.Context) -> None:
    """Registered agents: binary / config / installed version."""
    if ctx.invoked_subcommand is None:
        _emit_agent_list(ctx)


@list_app.command("config")
def list_config_cmd(
    ctx: typer.Context,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            "-k",
            help="Filter: skill, bundle, mcp, tool, rule, config, addon.",
            autocompletion=_plugin_kind_completer,
        ),
    ] = None,
) -> None:
    """List skills/MCP/addons from the plugin registry."""
    _print_config_plugins(get_opts(ctx).json, kind=kind)


@agent_app.command("setup")
def agent_setup_cmd(
    ctx: typer.Context,
    bundle: Annotated[
        list[str] | None,
        typer.Argument(
            help="Config bundle(s) or registered agent id(s). "
            "With --project, first arg is the target directory.",
            autocompletion=_bundle_completer,
        ),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
    list_bundles: Annotated[
        bool,
        typer.Option("--list", "-l", help="List config bundles (not installable CLIs)."),
    ] = False,
    all_agents: Annotated[
        bool,
        typer.Option("--all", help="Registry-driven setup for every installed agent."),
    ] = False,
    post_install: Annotated[
        bool,
        typer.Option(
            "--post-install",
            help="Run the agent's interactive setup.post_install (e.g. openclaw onboard).",
        ),
    ] = False,
    project: Annotated[
        bool,
        typer.Option(
            "--project",
            help="Scaffold AGENTS.md + .cursor/ in a repo "
            "(DIR = first arg or --path; not the `project` config bundle).",
        ),
    ] = False,
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Project directory for --project (default: cwd)."),
    ] = None,
) -> None:
    """Write MCP, rules, and skills configs (or --project for per-repo scaffold)."""
    opts = get_opts(ctx)

    if project:
        names = list(bundle) if bundle else []
        if path is not None:
            project_dir = path.expanduser().resolve()
            if names:
                ui.print_warn(f"--path set; ignoring positional args: {', '.join(names)}")
        elif names:
            project_dir = Path(names[0]).expanduser().resolve()
            if len(names) > 1:
                ui.print_warn(f"--project ignores extra args: {', '.join(names[1:])}")
        else:
            project_dir = Path.cwd().resolve()
        try:
            result = agent_setup_mod.agent_setup(
                mode="project",
                project_dir=project_dir,
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
            ui.print_ok(f"Project templates installed in {project_dir}")
        else:
            for err in result.errors:
                ui.print_error(err)
            raise typer.Exit(result.exit_code)
        return

    if list_bundles:
        _print_bundles(opts.json)
        return

    from astroai_lab.agent.registry import (
        list_installed_registry_agents,
        registry_ids,
        setup_registry_agent,
    )

    names = list(bundle) if bundle else []
    registry = registry_ids()
    if all_agents:
        agent_ids = [a["id"] for a in list_installed_registry_agents()]
        bundle_names: list[str] = []
        if names:
            ui.print_warn(f"--all ignores bundle names: {', '.join(names)}")
    else:
        agent_ids = [n for n in names if n in registry]
        bundle_names = [n for n in names if n not in registry]

    agent_actions: list[str] = []
    agent_errors: list[str] = []
    for agent_id in agent_ids:
        try:
            res = setup_registry_agent(
                agent_id,
                force=force or opts.yes,
                dry_run=opts.dry_run,
                post_install=post_install,
            )
        except LabError as exc:
            agent_errors.append(f"{agent_id}: {exc}")
            continue
        agent_actions.extend(res["actions"])
        agent_errors.extend(res["errors"])

    if agent_ids or all_agents:
        bundle_result = None
        if bundle_names:
            try:
                bundle_result = agent_setup_mod.agent_setup(
                    mode="install",
                    bundles=bundle_names,
                    force=force or opts.yes,
                    dry_run=opts.dry_run,
                )
            except LabError as exc:
                agent_errors.append(f"bundles: {exc}")
        if bundle_result is not None:
            payload = bundle_result.to_dict()
            payload["actions"] = agent_actions + payload["actions"]
            payload["errors"] = agent_errors + payload["errors"]
        else:
            payload = {
                "ok": not agent_errors,
                "partial": bool(agent_actions) and bool(agent_errors),
                "mode": "install",
                "actions": agent_actions,
                "errors": agent_errors,
                "warnings": [],
                "stamp": None,
            }
        ok = payload["ok"] and not agent_errors
        partial = payload["partial"] or (bool(agent_actions) and bool(agent_errors))
        payload["ok"] = ok
        payload["partial"] = partial
        exit_code = 0 if ok and not partial else (2 if (partial or payload["actions"]) else 1)
        if opts.json:
            ui.print_json(payload)
            if exit_code:
                raise typer.Exit(exit_code)
            return
        for err in payload["errors"]:
            ui.print_error(err)
        if ok and not partial:
            ui.print_ok("Agent setup complete")
        elif partial:
            ui.print_warn(
                f"Partial setup — {len(payload['actions'])} ok, {len(payload['errors'])} failed"
            )
        else:
            ui.print_error("Agent setup failed")
        if all_agents and not agent_ids:
            ui.print_hint("  No installed registry agents — install one: agent install <id>")
        if agent_ids:
            ui.print_hint("  astroai-lab agent verify        # confirm configs are healthy")
            ui.print_hint("  astroai-lab agent config <id>   # show/edit an agent's config")
        if exit_code:
            raise typer.Exit(exit_code)
        return

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
    ui.print_hint("  astroai-lab agent install kilo|goose|cline|opencode")
    ui.print_hint("  astroai-lab agent plugins install ponytail")
    ui.print_hint("  astroai-lab agent models free")
    if result.exit_code:
        raise typer.Exit(result.exit_code)


@agent_app.command("update")
def agent_update_cmd(
    ctx: typer.Context,
    agent: Annotated[
        str | None,
        typer.Argument(
            help="Registered agent id (registry-driven update).",
            autocompletion=_agent_completer,
        ),
    ] = None,
    reinstall: Annotated[
        bool,
        typer.Option("--reinstall", help="Force CLI reinstall even when the binary is up to date."),
    ] = False,
) -> None:
    """Refresh agent MCP, rules, skills, and GitHub skill clones."""
    if agent:
        _run_registry_agent_update(ctx, agent, reinstall=reinstall)
        return
    _run_agent_sync(ctx)


def _run_registry_agent_update(ctx: typer.Context, agent: str, *, reinstall: bool) -> None:
    from astroai_lab.agent.registry import update_registry_agent

    opts = get_opts(ctx)
    try:
        result = update_registry_agent(agent, force_reinstall=reinstall, dry_run=opts.dry_run)
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "agent": agent, "actions": [], "errors": [str(exc)]})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(result)
        if not result["ok"]:
            raise typer.Exit(2 if result["partial"] else 1)
        return
    prefix = "would" if opts.dry_run else ""
    for action in result["actions"]:
        ui.print_ok(f"{prefix} {action}")
    for err in result["errors"]:
        ui.print_error(err)
    if not result["ok"]:
        raise typer.Exit(2 if result["partial"] else 1)
    ui.print_ok(f"Agent {agent} updated")


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


def _run_registry_repair(ctx: typer.Context, agent_id: str | None, *, all_agents: bool) -> None:
    from astroai_lab.agent.registry import (
        fix_registry_agent,
        list_installed_registry_agents,
    )

    opts = get_opts(ctx)
    ids = [agent_id] if agent_id else [a["id"] for a in list_installed_registry_agents()]
    if not ids:
        if opts.json:
            ui.print_json(
                {
                    "ok": True,
                    "partial": False,
                    "agents": [],
                    "fixed": [],
                    "actions": [],
                    "errors": [],
                }
            )
        else:
            ui.print_hint("No installed registry agents — install one: agent install <id>")
        return

    actions: list[str] = []
    errors: list[str] = []
    fixed: list[str] = []
    for aid in ids:
        try:
            result = fix_registry_agent(aid, dry_run=opts.dry_run)
        except LabError as exc:
            errors.append(f"{aid}: {exc}")
            continue
        actions.extend(result["actions"])
        errors.extend(result["errors"])
        if result["ok"]:
            fixed.append(aid)

    payload = {
        "ok": not errors,
        "partial": bool(actions) and bool(errors),
        "agents": ids,
        "fixed": fixed,
        "actions": actions,
        "errors": errors,
    }
    if agent_id:
        payload["agent"] = agent_id
    if opts.json:
        ui.print_json(payload)
        if errors:
            raise typer.Exit(2 if payload["partial"] else 1)
        return
    for action in actions:
        ui.print_ok(f"  {action}")
    for err in errors:
        ui.print_error(f"  {err}")
    if errors:
        raise typer.Exit(2 if payload["partial"] else 1)
    if agent_id:
        ui.print_ok(f"Agent {agent_id} config OK")
    else:
        ui.print_ok(f"Agent configs OK ({len(fixed)} agent(s))")


@agent_app.command("config")
def agent_config_cmd(
    ctx: typer.Context,
    agent: Annotated[
        str,
        typer.Argument(help="Registered agent id.", autocompletion=_agent_completer),
    ],
    pairs: Annotated[
        list[str] | None,
        typer.Argument(help="key=value pairs to write (dotted keys allowed)."),
    ] = None,
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="Show one dotted key value instead of the whole file."),
    ] = None,
    unset: Annotated[
        list[str] | None,
        typer.Option("--unset", "-u", help="Remove a dotted key (repeatable)."),
    ] = None,
) -> None:
    """Show or edit a registered agent's config file."""
    from astroai_lab.agent import agent_config as agent_config_mod

    opts = get_opts(ctx)
    set_items: dict[str, Any] = {}
    for raw in pairs or []:
        if "=" not in raw:
            raise typer.BadParameter(f"expected key=value, got {raw!r}")
        k, _, v = raw.partition("=")
        set_items[k.strip()] = agent_config_mod.parse_value(v)
    unsets = list(unset or [])

    try:
        if set_items or unsets:
            actions = agent_config_mod.edit_agent_config(
                agent, set_items=set_items, unsets=unsets, dry_run=opts.dry_run
            )
        elif key:
            value, found = agent_config_mod.get_config_value(agent, key)
            if not found:
                raise LabError(f"{agent} has no key {key!r}")
            if opts.json:
                ui.print_json({"agent": agent, "key": key, "value": value})
            else:
                ui.print_ok(f"{key} = {agent_config_mod.fmt_value(value)}")
            return
        else:
            path, data = agent_config_mod.read_agent_config(agent)
            if opts.json:
                ui.print_json(
                    {
                        "agent": agent,
                        "path": str(path),
                        "format": agent_config_mod.config_format(agent),
                        "data": data,
                    }
                )
            else:
                ui.print_hint(f"{agent} config — {path}")
                typer.echo(path.read_text(encoding="utf-8").rstrip() or "(empty)")
            return
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "agent": agent, "errors": [str(exc)]})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc

    if opts.json:
        ui.print_json(
            {
                "agent": agent,
                "actions": actions,
                "dry_run": opts.dry_run,
                "ok": not any(a["status"] in ("error",) for a in actions),
            }
        )
        return
    prefix = "would" if opts.dry_run else ""
    for a in actions:
        if a["status"] == "set":
            ui.print_ok(f"set {a['key']} = {a['detail']}")
        elif a["status"] == "unset":
            ui.print_ok(f"unset {a['key']}")
        elif a["status"] == "would_set":
            ui.print_ok(f"{prefix} set {a['key']} = {a['detail']}")
        elif a["status"] == "would_unset":
            ui.print_ok(f"{prefix} unset {a['key']}")
        else:
            ui.print_hint(f"{a['key']}: {a['detail']}")
    ui.print_ok("Config updated")


@agent_app.command("status")
def agent_status_cmd(
    ctx: typer.Context,
    ui_endpoints: Annotated[
        bool,
        typer.Option("--ui", help="Show active container UI endpoints."),
    ] = False,
) -> None:
    """Show which agents are installed, configured, and have issues."""
    from astroai_lab.agent.setup_state import build_agent_report, read_setup_state

    opts = get_opts(ctx)
    if ui_endpoints:
        _print_interact(opts)
        return
    home = Path.home()
    report = build_agent_report(home)
    if opts.json:
        ui.print_json(report)
        if not report.get("ok"):
            raise typer.Exit(1)
        return
    state = read_setup_state(home)
    _print_status_table(report, stamp=state.stamp, failed=state.failed)


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
    """Check agent setup: required files plus JSON/TOML/YAML syntax of configs."""
    from astroai_lab.agent import inventory as agent_inventory
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
        ui.print_hint("Tip: Run `astroai-lab agent repair` or `astroai-lab agent verify --fix`.")
        raise typer.Exit(1)
    if state.stamp:
        ui.print_hint(f"  last run: {state.stamp}")
    ui.print_ok("Agent setup OK")


@agent_app.command("repair")
def agent_repair_cmd(
    ctx: typer.Context,
    agent: Annotated[
        str | None,
        typer.Argument(
            help="Registered agent id (registry-driven config repair).",
            autocompletion=_agent_completer,
        ),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Clean stale state instead of auto-repairing."),
    ] = False,
    all_agents: Annotated[
        bool,
        typer.Option("--all", help="Registry-driven config repair for every installed agent."),
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
    """Auto-repair agent setup (or `--clean` stale state)."""
    from astroai_lab.cli.context import merge_opts

    opts = merge_opts(ctx, dry_run=dry_run)
    if agent or all_agents:
        if clean:
            raise typer.BadParameter("--clean cannot be combined with <agent> or --all")
        _run_registry_repair(ctx, agent, all_agents=all_agents)
        return
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
        ui.print_ok(f"Agent setup repair complete ({fixed_count} item(s) {prefix})")
    else:
        ui.print_ok("Agent setup already healthy")


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
    """Install AI coding CLIs to $ASTROAI_LAB_BIN_DIR (scratch/team, not $HOME)."""
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
            raise LabError(f"Unknown tool: {tool}", hint="astroai-lab agent list")
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
        typer.Argument(help="Tool/agent name.", autocompletion=_tool_completer),
    ],
    purge: Annotated[
        bool,
        typer.Option("--purge", help="Also remove the agent's home dir (~/.hermes, ~/.openclaw)."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Uninstall an agent CLI: binary, config files, plugin files, setup stamps."""
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


@agent_app.command("wipe")
def agent_wipe_cmd(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Factory reset: remove EVERY agent binary, config, plugin, and setup state."""
    from astroai_lab.agent.wipe import wipe_agent_state
    from astroai_lab.cli.context import merge_opts

    opts = merge_opts(ctx, yes=yes, dry_run=dry_run)

    if opts.json and not opts.yes and not opts.dry_run:
        ui.print_json(
            {
                "ok": False,
                "dry_run": False,
                "actions": [],
                "errors": [
                    "agent wipe --json requires --yes (no interactive prompt in machine mode)"
                ],
                "counts": {"removed": 0, "would_remove": 0, "errors": 1},
            }
        )
        raise typer.Exit(1)

    if not opts.dry_run and not opts.yes and not opts.json:
        ui.print_warn("This PERMANENTLY removes every agent configuration:")
        ui.print_warn("  • every installed agent CLI (binary + config + plugins + home dirs)")
        ui.print_warn("  • ~/.astroai/lab setup state (stamps, locks, logs)")
        ui.print_warn("  • Cursor skills, rules, and MCP configs (~/.cursor)")
        ui.print_warn("Saved environments, projects, and CANFAR config are NOT touched.")
        if not typer.confirm("Proceed with the full wipe?", default=False):
            ui.print_hint("Wipe cancelled.")
            raise typer.Exit(0)

    results = wipe_agent_state(dry_run=opts.dry_run)
    errors = [r for r in results if r["status"] == "error"]
    removed = [r for r in results if r["status"] == "removed"]
    would = [r for r in results if r["status"] == "would_remove"]

    if opts.json:
        ui.print_json(
            {
                "ok": not errors,
                "dry_run": opts.dry_run,
                "actions": results,
                "errors": [r["detail"] for r in errors],
                "counts": {
                    "removed": len(removed),
                    "would_remove": len(would),
                    "errors": len(errors),
                },
            }
        )
        if errors:
            raise typer.Exit(1)
        return

    prefix = "would remove" if opts.dry_run else "removed"
    for r in results:
        if r["status"] == "error":
            ui.print_error(f"  {r['target']}: {r['detail']}")
        else:
            ui.print_ok(f"  {r['target']}: {prefix} ({r['detail']})")
    if errors:
        ui.print_error(f"Wipe finished with {len(errors)} error(s)")
        raise typer.Exit(1)
    if not results:
        ui.print_ok("Nothing to wipe — agent layer already clean")
        return
    if opts.dry_run:
        ui.print_ok(f"Would remove {len(would)} item(s) — run without --dry-run to apply")
        return
    ui.print_ok("Agent layer wiped — restart from scratch with: astroai-lab agent setup")


# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------

plugins_app = typer.Typer(
    help="Plugins: skills/MCP/config across installed agents (data/agent/plugins/*.yaml)."
)
agent_app.add_typer(plugins_app, name="plugins")


@plugins_app.callback(invoke_without_command=True)
def plugins_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _print_plugins(get_opts(ctx).json)


@plugins_app.command("list")
def plugins_list_cmd(
    ctx: typer.Context,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            "-k",
            help="Filter: skill, bundle, mcp, tool, rule, config, addon.",
            autocompletion=_plugin_kind_completer,
        ),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Only plugins applied to this agent."),
    ] = None,
) -> None:
    """List installed + available plugins."""
    _print_plugins(get_opts(ctx).json, kind=kind, agent=agent)


@plugins_app.command("install")
def plugins_install_cmd(
    ctx: typer.Context,
    plugin: Annotated[str, typer.Argument(autocompletion=_plugin_completer)],
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Scope to one agent."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Install a plugin on every installed agent that supports it."""
    opts = get_opts(ctx)
    try:
        results = agent_plugins.install_plugin(
            plugin,
            agent=agent,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "plugin": plugin, "actions": [], "errors": [str(exc)]})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": not any(r.status == "failed" for r in results),
                "plugin": plugin,
                "actions": [r.__dict__ for r in results],
                "errors": [r.detail for r in results if r.status == "failed"],
                "dry_run": opts.dry_run,
            }
        )
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return
    _print_plugin_results(results, verb="install", dry_run=opts.dry_run)


@plugins_app.command("update")
def plugins_update_cmd(
    ctx: typer.Context,
    plugin: Annotated[str, typer.Argument(autocompletion=_plugin_completer)],
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Scope to one agent."),
    ] = None,
) -> None:
    """Refresh a plugin: re-apply to every installed agent that supports it."""
    opts = get_opts(ctx)
    try:
        results = agent_plugins.update_plugin(plugin, agent=agent, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": not any(r.status == "failed" for r in results),
                "plugin": plugin,
                "actions": [r.__dict__ for r in results],
                "errors": [r.detail for r in results if r.status == "failed"],
                "dry_run": opts.dry_run,
            }
        )
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return
    _print_plugin_results(results, verb="update", dry_run=opts.dry_run)


@plugins_app.command("remove")
def plugins_remove_cmd(
    ctx: typer.Context,
    plugin: Annotated[str, typer.Argument(autocompletion=_plugin_completer)],
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Scope to one agent."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show actions without executing.")
    ] = False,
) -> None:
    """Remove a plugin from every agent (or one ``--agent``)."""
    from astroai_lab.cli.context import merge_opts

    opts = merge_opts(ctx, dry_run=dry_run)
    try:
        results = agent_plugins.remove_plugin(plugin, agent=agent, dry_run=opts.dry_run)
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "plugin": plugin, "actions": [], "errors": [str(exc)]})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": not any(r.status == "failed" for r in results),
                "plugin": plugin,
                "actions": [r.__dict__ for r in results],
                "errors": [r.detail for r in results if r.status == "failed"],
                "dry_run": opts.dry_run,
            }
        )
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return
    _print_plugin_results(results, verb="remove", dry_run=opts.dry_run)


@plugins_app.command("configure")
def plugins_configure_cmd(
    ctx: typer.Context,
    plugin: Annotated[str, typer.Argument(autocompletion=_plugin_completer)],
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Scope to one agent."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Per-agent config merge (kind: mcp) or config write (kind: config)."""
    opts = get_opts(ctx)
    try:
        results = agent_plugins.configure_plugin(
            plugin, agent=agent, force=force or opts.yes, dry_run=opts.dry_run
        )
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "plugin": plugin, "actions": [], "errors": [str(exc)]})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json(
            {
                "ok": not any(r.status == "failed" for r in results),
                "plugin": plugin,
                "actions": [r.__dict__ for r in results],
                "errors": [r.detail for r in results if r.status == "failed"],
                "dry_run": opts.dry_run,
            }
        )
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return
    _print_plugin_results(results, verb="configure", dry_run=opts.dry_run)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

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
    """Apply free-tier model configs for goose, kilo, opencode, codex, cline."""
    opts = get_opts(ctx)
    try:
        actions = agent_free_models.apply_free_models(
            preset=preset,
            force=force or opts.yes,
            dry_run=opts.dry_run,
        )
    except LabError as exc:
        if opts.json:
            ui.print_json({"ok": False, "preset": preset, "actions": [], "errors": [str(exc)]})
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
