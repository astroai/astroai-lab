"""Command-line interface for canfar-lab."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Optional

import typer

from canfar_lab import __version__
from canfar_lab import ui
from canfar_lab.paths import quota_used_pct, resolve_paths
from canfar_lab.project import (
    ProjectError,
    bootstrap_lock,
    detect_project,
    format_dir_size,
    install_project,
    list_saves,
    require_project,
    resolve_save_dir,
    restore_env,
    run,
    save_env,
    warm_cache,
    which,
)
from canfar_lab.utils.console import console

app = typer.Typer(
    name="canfar-lab",
    help="CANFAR Science Platform in-session workbench.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
    epilog="Platform client: [bold]canfar[/bold] — https://opencadc.github.io/canfar/",
)
env_app = typer.Typer(help="Save and resume pixi/uv lockfile environments.")
project_app = typer.Typer(help="Start new projects under the work directory.")
app.add_typer(env_app, name="env")
app.add_typer(project_app, name="project")

TOOL_NAMES = ("git", "gh", "pixi", "uv", "jq", "rg", "canfar")


def _handle_error(exc: ProjectError) -> None:
    ui.print_error(str(exc))
    raise typer.Exit(code=1) from exc


@app.callback()
def main(ctx: typer.Context) -> None:
    """In-session workbench for code, environments, and storage paths."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def version() -> None:
    """Show version."""
    typer.echo(f"canfar-lab {__version__}")


@app.command()
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output."),
    ] = False,
) -> None:
    """Show session paths, quotas, and tool availability.

    Examples:
        canfar-lab doctor
        canfar-lab doctor --json
    """
    paths = resolve_paths()
    tools = {name: which(name) is not None for name in TOOL_NAMES}
    report = ui.DoctorReport(
        work_dir=str(paths.work_dir),
        scratch_dir=str(paths.scratch_dir) if paths.scratch_dir else None,
        save_dir=str(paths.save_dir),
        config_dir=str(paths.config_dir),
        home=str(paths.home),
        arc_projects=str(paths.arc_projects) if paths.arc_projects else None,
        pixi_cache_dir=str(paths.pixi_cache_dir) if paths.pixi_cache_dir else None,
        uv_cache_dir=str(paths.uv_cache_dir) if paths.uv_cache_dir else None,
        home_quota_pct=quota_used_pct(paths.home),
        tools=tools,
    )
    if json_output:
        ui.print_json(asdict(report))
        return
    ui.doctor_human(report)


@app.command()
def clone(
    repo: Annotated[str, typer.Argument(help="GitHub repo as owner/name.")],
    target: Annotated[
        Optional[Path],
        typer.Argument(help="Clone destination (default: work_dir/<repo-name>)."),
    ] = None,
    from_env: Annotated[
        Optional[str],
        typer.Option("--from-env", help="Saved env name for cache warm / lock bootstrap."),
    ] = None,
    from_path: Annotated[
        Optional[Path],
        typer.Option("--from", help="Custom save directory (with --from-env)."),
    ] = None,
) -> None:
    """Clone a GitHub repo and install project dependencies.

    Examples:
        canfar-lab clone myorg/myproject
        canfar-lab clone --from-env ml-base myorg/myproject
        canfar-lab clone myorg/myproject /srcdir/custom
    """
    if from_path and not from_env:
        ui.print_error("--from requires --from-env <name>")
        raise typer.Exit(code=1)

    if which("gh") is None:
        ui.print_error("gh (GitHub CLI) is required.\n  gh auth login")
        raise typer.Exit(code=1)

    paths = resolve_paths()
    repo_name = repo.rsplit("/", 1)[-1]
    dest = target or paths.work_dir / repo_name

    if dest.exists():
        ui.print_error(f"Target already exists: {dest}")
        raise typer.Exit(code=1)

    save_dir: Path | None = None
    if from_env:
        try:
            save_dir = resolve_save_dir(from_env, paths.save_dir, from_path)
        except ProjectError as exc:
            _handle_error(exc)
        ui.print_info(f"Warming caches from saved env '{from_env}'...")
        try:
            warm_cache(save_dir)
        except ProjectError as exc:
            _handle_error(exc)

    ui.print_info(f"Cloning {repo} -> {dest}...")
    try:
        run(["gh", "repo", "clone", repo, str(dest)])
    except ProjectError as exc:
        _handle_error(exc)

    kind = detect_project(dest)
    try:
        bootstrap = False
        if save_dir and kind:
            bootstrap = bootstrap_lock(save_dir, dest)
            if bootstrap:
                ui.print_hint("Bootstrap: copied lockfile from saved env (session-local).")
                ui.print_hint("Publish for OSS: pixi lock && git add pixi.lock && git commit")

        if kind:
            ui.print_info(f"Installing {kind.value} environment...")
            install_project(dest, bootstrap_lock=bootstrap)
        else:
            ui.print_hint("No pixi.toml or pyproject.toml — skipping dependency install.")
            ui.print_hint("  canfar-lab project new mylab")
    except ProjectError as exc:
        _handle_error(exc)

    ui.print_ok(f"Ready: cd {dest}")
    if kind:
        cmd = "pixi run python script.py" if kind.value == "pixi" else "uv run python script.py"
        ui.print_hint(f"  {cmd}")


@env_app.command("save")
def env_save(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Save name (default: current directory name)."),
    ] = None,
    to: Annotated[
        Optional[Path],
        typer.Option("--to", help="Custom save directory."),
    ] = None,
) -> None:
    """Save lockfiles and manifest for the current pixi/uv project.

    Examples:
        canfar-lab env save
        canfar-lab env save mylab
        canfar-lab env save mylab --to /arc/projects/group/env-saves/mylab
    """
    paths = resolve_paths()
    cwd = Path.cwd()
    save_name = name or cwd.name
    save_dir = to if to else paths.save_dir / save_name

    try:
        require_project(cwd)
        save_env(save_name, save_dir, cwd)
    except ProjectError as exc:
        _handle_error(exc)

    ui.print_ok(f"Saved '{save_name}' -> {save_dir} ({format_dir_size(save_dir)})")
    ui.print_hint(f"  canfar-lab env resume {save_name}")


@env_app.command("resume")
def env_resume(
    name: Annotated[str, typer.Argument(help="Save name to restore.")],
    target: Annotated[
        Optional[Path],
        typer.Argument(help="Restore target (default: work_dir/<name>)."),
    ] = None,
    from_path: Annotated[
        Optional[Path],
        typer.Option("--from", help="Custom save directory."),
    ] = None,
) -> None:
    """Restore a saved environment and rebuild with pixi install / uv sync.

    Examples:
        canfar-lab env resume mylab
        canfar-lab env resume mylab /srcdir/mylab
        canfar-lab env resume mylab --from /arc/projects/group/env-saves/mylab
    """
    paths = resolve_paths()
    dest = target or paths.work_dir / name

    try:
        save_dir = resolve_save_dir(name, paths.save_dir, from_path)
        restore_env(save_dir, dest)
    except ProjectError as exc:
        _handle_error(exc)

    ui.print_ok(f"Environment restored in {dest}")
    ui.print_hint(f"  cd {dest}")


@env_app.command("list")
def env_list(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output."),
    ] = False,
) -> None:
    """List saved environments.

    Examples:
        canfar-lab env list
        canfar-lab env list --json
    """
    paths = resolve_paths()
    rows = [
        {
            "name": manifest.name,
            "kind": manifest.kind.value,
            "saved_at": manifest.saved_at,
            "path": str(entry),
            "full": str(manifest.full).lower(),
        }
        for entry, manifest in list_saves(paths.save_dir)
    ]
    if json_output:
        ui.print_json(rows)
        return
    ui.env_list_table(rows)


@project_app.command("new")
def project_new(
    name: Annotated[str, typer.Argument(help="Project directory name under work dir.")],
    uv_project: Annotated[
        bool,
        typer.Option("--uv", help="Use uv instead of pixi."),
    ] = False,
) -> None:
    """Create a new pixi or uv project under the work directory.

    Examples:
        canfar-lab project new mylab
        canfar-lab project new mylab --uv
    """
    paths = resolve_paths()
    target = paths.work_dir / name

    if target.exists() and any(target.iterdir()):
        ui.print_error(f"Directory exists and is not empty: {target}")
        raise typer.Exit(code=1)

    target.mkdir(parents=True, exist_ok=True)

    try:
        if uv_project:
            run(["uv", "init", "--no-readme"], cwd=target)
        else:
            run(["pixi", "init", "--no-progress"], cwd=target)
    except ProjectError as exc:
        _handle_error(exc)

    ui.print_ok(f"Project ready: {target}")
    ui.print_hint(f"  cd {target}")
    if uv_project:
        ui.print_hint("  uv add numpy")
    else:
        ui.print_hint("  pixi add python numpy")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
