from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from canfar_lab import ui
from canfar_lab.cli.context import get_opts, merge_opts
from canfar_lab.config.settings import get_settings
from canfar_lab.core.git import git_init_and_commit, git_push, git_status
from canfar_lab.core.paths import resolve_paths
from canfar_lab.core.project import detect_project, format_dir_size, require_project, save_env
from canfar_lab.errors import LabError


def _init_impl(
    ctx: typer.Context,
    name: str,
    uv_project: bool,
    no_git: bool,
    no_gh: bool,
) -> None:
    from canfar_lab.core.project import init_project

    opts = get_opts(ctx)
    settings = get_settings()
    if not uv_project and settings.default_pm == "uv":
        uv_project = True
    paths = resolve_paths()
    target = paths.work_dir / name
    if target.exists() and any(target.iterdir()):
        ui.print_error(f"Directory exists and is not empty: {target}")
        raise typer.Exit(1)
    try:
        with ui.progress_task("Initializing project...", quiet=opts.quiet):
            kind = init_project(target, use_uv=uv_project)
            if not no_git:
                git_init_and_commit(target)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    ui.print_ok(f"Project ready: {target}")
    ui.print_hint(f"  `cd {target}`")
    ui.print_hint("  `pixi add python numpy`" if kind.value == "pixi" else "  `uv add numpy`")
    if not no_gh and shutil.which("gh") and not no_git:
        ui.print_hint(f"  `gh repo create {name} --private --source=. --push`")


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init_cmd(
        ctx: typer.Context,
        name: Annotated[str, typer.Argument(help="Project directory name.")],
        uv_project: Annotated[bool, typer.Option("--uv")] = False,
        no_git: Annotated[bool, typer.Option("--no-git")] = False,
        no_gh: Annotated[bool, typer.Option("--no-gh")] = False,
    ) -> None:
        """Create a new pixi or uv project under the work directory.

        Examples:
            canfar-lab init mylab
            canfar-lab init mylab --uv
        """
        _init_impl(ctx, name, uv_project, no_git, no_gh)

    @app.command("project-new", hidden=True)
    def project_new_alias(
        ctx: typer.Context,
        name: Annotated[str, typer.Argument()],
        uv_project: Annotated[bool, typer.Option("--uv")] = False,
        no_git: Annotated[bool, typer.Option("--no-git")] = False,
        no_gh: Annotated[bool, typer.Option("--no-gh")] = False,
    ) -> None:
        _init_impl(ctx, name, uv_project, no_git, no_gh)

    @app.command()
    def clone(
        ctx: typer.Context,
        repo: Annotated[str, typer.Argument(help="GitHub repo as owner/name.")],
        target: Annotated[Path | None, typer.Argument()] = None,
        from_env: Annotated[str | None, typer.Option("--from-env")] = None,
        from_path: Annotated[Path | None, typer.Option("--from")] = None,
    ) -> None:
        """Clone a GitHub repo and install dependencies.

        Examples:
            canfar-lab clone myorg/myproject
            canfar-lab clone --from-env ml-base myorg/myproject
        """
        from canfar_lab.core.project import (
            bootstrap_lock,
            detect_project,
            install_project,
            resolve_save_dir,
            warm_cache,
        )
        from canfar_lab.utils.subprocess import run

        opts = get_opts(ctx)
        settings = get_settings()
        from_env = from_env or settings.clone_from_env
        if from_path and not from_env:
            ui.print_error("--from requires --from-env <name>")
            raise typer.Exit(1)
        if shutil.which("gh") is None:
            ui.print_error("gh required.\n  `gh auth login`")
            raise typer.Exit(1)
        paths = resolve_paths()
        dest = target or paths.work_dir / repo.rsplit("/", 1)[-1]
        if dest.exists():
            ui.print_error(f"Target already exists: {dest}")
            raise typer.Exit(1)
        try:
            save_dir: Path | None = None
            if from_env:
                save_dir = resolve_save_dir(from_env, paths.save_dir, from_path)
                with ui.progress_task(f"Warming caches from '{from_env}'...", quiet=opts.quiet):
                    warm_cache(save_dir)
            with ui.progress_task(f"Cloning {repo}...", quiet=opts.quiet):
                run(["gh", "repo", "clone", repo, str(dest)])
            kind = detect_project(dest)
            bootstrap = bool(save_dir and kind and bootstrap_lock(save_dir, dest))
            if kind:
                with ui.progress_task(f"Installing {kind.value}...", quiet=opts.quiet):
                    install_project(dest, bootstrap_lock=bootstrap, quiet=opts.quiet)
        except LabError as exc:
            ui.print_error(str(exc))
            raise typer.Exit(1) from exc
        ui.print_ok(f"Ready: `cd {dest}`")

    @app.command()
    def save(
        ctx: typer.Context,
        name: Annotated[str | None, typer.Argument()] = None,
        to: Annotated[Path | None, typer.Option("--to")] = None,
        full: Annotated[bool, typer.Option("--full")] = False,
    ) -> None:
        """Save lockfiles and manifest for the current project.

        Examples:
            canfar-lab save
            canfar-lab save mylab --full
        """
        paths = resolve_paths()
        cwd = Path.cwd()
        save_name = name or cwd.name
        save_dir = to or paths.save_dir / save_name
        try:
            require_project(cwd)
            save_env(save_name, save_dir, cwd, full=full)
        except LabError as exc:
            ui.print_error(str(exc))
            raise typer.Exit(1) from exc
        ui.print_ok(f"Saved '{save_name}' -> {save_dir} ({format_dir_size(save_dir)})")

    @app.command()
    def resume(
        ctx: typer.Context,
        name: Annotated[str, typer.Argument()],
        target: Annotated[Path | None, typer.Argument()] = None,
        from_path: Annotated[Path | None, typer.Option("--from")] = None,
    ) -> None:
        """Restore a saved environment.

        Examples:
            canfar-lab resume mylab
            canfar-lab resume mylab --from /arc/projects/group/env-saves/mylab
        """
        from canfar_lab.core.project import resolve_save_dir, restore_env

        opts = get_opts(ctx)
        paths = resolve_paths()
        dest = target or paths.work_dir / name
        try:
            save_dir = resolve_save_dir(name, paths.save_dir, from_path)
            with ui.progress_task("Restoring environment...", quiet=opts.quiet):
                restore_env(save_dir, dest)
        except LabError as exc:
            ui.print_error(str(exc))
            raise typer.Exit(1) from exc
        ui.print_ok(f"Restored in {dest}")
        ui.print_hint(f"  `cd {dest}`")

    @app.command()
    def saves(
        ctx: typer.Context,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """List saved environments.

        Examples:
            canfar-lab saves
            canfar-lab saves --json
            canfar-lab --json saves
        """
        from canfar_lab.core.project import save_rows

        opts = merge_opts(ctx, json_output=json_output)
        paths = resolve_paths()
        rows = save_rows(paths.save_dir)
        if opts.json:
            ui.print_json(rows)
        else:
            ui.env_list_table(rows)

    @app.command()
    def push(
        ctx: typer.Context,
        name: Annotated[str | None, typer.Option("--name", help="Env save name.")] = None,
        yes: Annotated[
            bool, typer.Option("--yes", "-y", help="Non-interactive; skip confirmations.")
        ] = False,
    ) -> None:
        """End-of-session archive: git push + env save.

        Examples:
            canfar-lab push
            canfar-lab push --yes
            canfar-lab --yes push
            canfar-lab push --name mylab
        """
        opts = merge_opts(ctx, yes=yes)
        settings = get_settings()
        paths = resolve_paths()
        cwd = Path.cwd()
        pushed = saved = False
        git = git_status(cwd)

        if git.in_repo:
            if git.uncommitted:
                ui.print_warn("Uncommitted changes detected.")
                ui.print_hint("  `git add -A && git commit -m 'session work'`")
                if settings.push.require_clean_git and not opts.yes:
                    raise typer.Exit(1)
            try:
                with ui.progress_task("Pushing to origin...", quiet=opts.quiet):
                    git_push(cwd)
                pushed = True
                ui.print_ok("git push done")
            except LabError as exc:
                ui.print_error(str(exc))
        else:
            ui.print_hint("Not in a git repo — skipping push.")

        if detect_project(cwd) and settings.push.auto_save:
            save_name = name or cwd.name
            save_dir = paths.save_dir / save_name
            try:
                require_project(cwd)
                save_env(save_name, save_dir, cwd)
                saved = True
                ui.print_ok(f"env saved: {save_name} ({format_dir_size(save_dir)})")
            except LabError as exc:
                ui.print_error(str(exc))
        elif not detect_project(cwd):
            ui.print_hint("No pixi/uv project — skipping env save.")

        if opts.json:
            ui.print_json({"pushed": pushed, "saved": saved, "work_dir": str(paths.work_dir)})
        elif not (pushed or saved):
            ui.print_warn(f"{paths.work_dir} is ephemeral — nothing archived.")
