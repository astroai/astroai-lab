from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import get_opts, merge_opts
from astroai_lab.config.settings import get_settings
from astroai_lab.core.git import git_init_and_commit
from astroai_lab.core.paths import resolve_paths
from astroai_lab.core.project import format_dir_size, require_project, save_env, save_rows
from astroai_lab.errors import LabError
from astroai_lab.utils.subprocess import run_capture

_DEFAULT_CLONE_ORG = "astroai"


def _gh_login() -> str | None:
    try:
        login = run_capture(["gh", "api", "user", "-q", ".login"])
    except LabError:
        return None
    return login or None


def _gh_repo_exists(spec: str) -> bool:
    result = subprocess.run(
        ["gh", "repo", "view", spec, "--json", "name"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def resolve_clone_spec(spec: str) -> str:
    """Pass through owner/name. A bare name tries $gh-user then astroai."""
    if "/" in spec:
        return spec
    owners: list[str] = []
    login = _gh_login()
    if login:
        owners.append(login)
    if _DEFAULT_CLONE_ORG not in owners:
        owners.append(_DEFAULT_CLONE_ORG)
    tried = [f"{owner}/{spec}" for owner in owners]
    for candidate in tried:
        if _gh_repo_exists(candidate):
            return candidate
    raise LabError(
        f"No GitHub repo {spec!r} under {' or '.join(tried)}",
        hint="Pass owner/name, or `gh auth login` so your user is tried first.",
    )


def _print_save_list(*, json_output: bool, root: Path) -> None:
    rows = save_rows(root)
    if json_output:
        ui.print_json(rows)
    else:
        ui.env_list_table(rows)


def _init_impl(
    ctx: typer.Context,
    name: str,
    uv_project: bool,
    no_git: bool,
    no_gh: bool,
) -> None:
    from astroai_lab.core.project import init_project

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
            astroai init mylab
            astroai init mylab --uv
        """
        _init_impl(ctx, name, uv_project, no_git, no_gh)

    @app.command()
    def clone(
        ctx: typer.Context,
        repos: Annotated[
            list[str] | None,
            typer.Argument(help="GitHub repo(s): owner/name, or a name (your user, then astroai)."),
        ] = None,
        to: Annotated[
            Path | None,
            typer.Option("--to", help="Destination directory (one repo only)."),
        ] = None,
        from_env: Annotated[str | None, typer.Option("--from-env")] = None,
        from_path: Annotated[Path | None, typer.Option("--from")] = None,
    ) -> None:
        """Clone GitHub repo(s) and install dependencies.

        Examples:
            astroai clone myproject
            astroai clone myorg/myproject
            astroai clone owner/a owner/b
            astroai clone --from-env ml-base myorg/myproject
            astroai clone owner/repo --to $WORK/custom
        """
        from astroai_lab.core.project import (
            bootstrap_lock,
            detect_project,
            install_project,
            resolve_save_dir,
            warm_cache,
        )
        from astroai_lab.utils.subprocess import run

        opts = get_opts(ctx)
        settings = get_settings()
        from_env = from_env or settings.clone_from_env
        names = list(repos or [])
        if to is None and len(names) >= 2 and "/" not in names[-1]:
            to = Path(names.pop())
        if not names:
            ui.print_error("clone needs a repo name")
            ui.print_hint("  astroai clone myproject")
            ui.print_hint("  astroai clone owner/repo")
            raise typer.Exit(1)
        if to is not None and len(names) != 1:
            ui.print_error("--to (or a target directory) only works with one repo")
            raise typer.Exit(1)
        if from_path and not from_env:
            ui.print_error("--from requires --from-env <name>")
            raise typer.Exit(1)
        if shutil.which("gh") is None:
            ui.print_error("gh required.\n  `gh auth login`")
            raise typer.Exit(1)
        paths = resolve_paths()
        jobs: list[tuple[str, Path]] = []
        for raw in names:
            try:
                repo = resolve_clone_spec(raw)
            except LabError as exc:
                ui.print_error(str(exc))
                raise typer.Exit(1) from exc
            dest = to if to is not None else paths.work_dir / repo.rsplit("/", 1)[-1]
            jobs.append((repo, dest))

        failed = 0
        save_dir: Path | None = None
        if opts.dry_run and from_env:
            ui.print_hint(f"  would warm caches from '{from_env}'")
        if from_env and not opts.dry_run:
            try:
                save_dir = resolve_save_dir(from_env, paths.save_dir, from_path)
                with ui.progress_task(f"Warming caches from '{from_env}'...", quiet=opts.quiet):
                    warm_cache(save_dir)
            except LabError as exc:
                ui.print_error(str(exc))
                raise typer.Exit(1) from exc

        for repo, dest in jobs:
            if dest.exists():
                ui.print_error(f"Target already exists: {dest}")
                failed += 1
                continue
            if opts.dry_run:
                ui.print_ok(f"dry-run: would clone {repo} -> {dest}")
                continue
            try:
                with ui.progress_task(f"Cloning {repo}...", quiet=opts.quiet):
                    run(["gh", "repo", "clone", repo, str(dest)])
                kind = detect_project(dest)
                bootstrap = bool(save_dir and kind and bootstrap_lock(save_dir, dest))
                if kind:
                    with ui.progress_task(f"Installing {kind.value}...", quiet=opts.quiet):
                        install_project(dest, bootstrap_lock=bootstrap, quiet=opts.quiet)
            except LabError as exc:
                ui.print_error(str(exc))
                failed += 1
                continue
            ui.print_ok(f"Ready: `cd {dest}`")
        if failed:
            raise typer.Exit(1)

    @app.command()
    def save(
        ctx: typer.Context,
        name: Annotated[str | None, typer.Argument()] = None,
        to: Annotated[
            Path | None,
            typer.Option("--to", help="Directory to write this snapshot."),
        ] = None,
        from_path: Annotated[
            Path | None,
            typer.Option("--from", help="With --list, directory to scan for snapshots."),
        ] = None,
        full: Annotated[
            bool, typer.Option("--full", help="Pack .pixi / .venv into the snapshot.")
        ] = False,
        list_flag: Annotated[
            bool,
            typer.Option("--list", "-l", help="List saved environments."),
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """Save the current project, or list snapshots.

        Examples:
            astroai save
            astroai save mylab --full
            astroai save mylab --to /arc/projects/group/env-saves/mylab
            astroai save --list
            astroai save --list --json
            astroai save --list --from /arc/projects/group/env-saves
        """
        opts = merge_opts(ctx, json_output=json_output)
        paths = resolve_paths()
        if list_flag:
            if name or to or full:
                ui.print_error("--list cannot be combined with NAME, --to, or --full")
                raise typer.Exit(1)
            _print_save_list(json_output=opts.json, root=from_path or paths.save_dir)
            return
        if from_path is not None:
            ui.print_error("--from is only valid with --list (use --to to choose where to write)")
            raise typer.Exit(1)
        cwd = Path.cwd()
        save_name = name or cwd.name
        save_dir = to or paths.save_dir / save_name
        try:
            kind = require_project(cwd)
            if opts.dry_run:
                if opts.json:
                    ui.print_json(
                        {
                            "dry_run": True,
                            "name": save_name,
                            "path": str(save_dir),
                            "kind": kind.value,
                            "full": full,
                        }
                    )
                else:
                    ui.print_ok(f"dry-run: would save '{save_name}' -> {save_dir} ({kind.value})")
                return
            save_env(save_name, save_dir, cwd, full=full)
            payload = {
                "name": save_name,
                "path": str(save_dir),
                "kind": kind.value,
                "full": full,
            }
        except (LabError, OSError) as exc:
            ui.print_error(str(exc))
            raise typer.Exit(1) from exc
        if opts.json:
            ui.print_json(payload)
        else:
            ui.print_ok(f"Saved '{save_name}' -> {save_dir} ({format_dir_size(save_dir)})")

    @app.command()
    def resume(
        ctx: typer.Context,
        name: Annotated[str, typer.Argument(help="Snapshot name.")],
        to: Annotated[
            Path | None,
            typer.Option("--to", help="Directory to restore into (default: $WORK/NAME)."),
        ] = None,
        from_path: Annotated[
            Path | None,
            typer.Option("--from", help="Snapshot directory, or a parent of named snapshots."),
        ] = None,
        yes: Annotated[
            bool, typer.Option("--yes", "-y", help="Replace a non-empty target.")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Machine-readable output.")
        ] = False,
    ) -> None:
        """Restore a saved environment.

        Examples:
            astroai resume mylab
            astroai resume mylab --yes
            astroai resume mylab --from /arc/projects/group/env-saves
            astroai resume mylab --to $WORK/mylab --from /arc/projects/group/env-saves/mylab
        """
        from astroai_lab.core.project import resolve_save_dir, restore_env

        opts = merge_opts(ctx, yes=yes, json_output=json_output)
        paths = resolve_paths()
        dest = to or paths.work_dir / name
        nonempty = dest.is_dir() and any(dest.iterdir())
        if dest.exists() and dest.is_file():
            ui.print_error(f"Target exists and is a file: {dest}")
            raise typer.Exit(1)
        if nonempty:
            ui.print_warn(f"Target exists and is not empty: {dest}")
            if not opts.yes and not opts.dry_run:
                ui.print_hint("  Use --yes to overwrite, or pass a different --to.")
                raise typer.Exit(1)
        try:
            save_dir = resolve_save_dir(name, paths.save_dir, from_path)
            if opts.dry_run:
                if opts.json:
                    ui.print_json(
                        {
                            "dry_run": True,
                            "name": name,
                            "from": str(save_dir),
                            "path": str(dest),
                            "replace": nonempty,
                        }
                    )
                else:
                    ui.print_ok(f"dry-run: would restore '{name}' -> {dest}")
                    if nonempty:
                        ui.print_hint(f"  would replace {dest}")
                return
            if nonempty:
                shutil.rmtree(dest)
            with ui.progress_task("Restoring environment...", quiet=opts.quiet):
                restore_env(save_dir, dest)
        except (LabError, OSError) as exc:
            ui.print_error(str(exc))
            raise typer.Exit(1) from exc
        if opts.json:
            ui.print_json({"name": name, "from": str(save_dir), "path": str(dest)})
        else:
            ui.print_ok(f"Restored in {dest}")
            ui.print_hint(f"  `cd {dest}`")
