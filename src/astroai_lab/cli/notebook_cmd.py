"""Copy starter notebooks into the session work or scratch directory."""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.core.paths import resolve_paths

notebook_app = typer.Typer(help="Starter notebooks for students.")

_IMAGE_STARTERS = Path("/opt/astroai/notebooks")

# name → filename under /opt/astroai/notebooks or package data
_STARTERS: dict[str, str] = {
    "starter": "starter.ipynb",
    "ray_train": "ray_train.ipynb",
    "marimo": "starter.py",
}


def _resolve_starter(filename: str) -> Path | None:
    src = _IMAGE_STARTERS / filename
    if src.is_file():
        return src
    try:
        pkg = importlib.resources.files("astroai_lab.data") / "notebooks" / filename
        path = Path(str(pkg))
    except (FileNotFoundError, TypeError, ModuleNotFoundError, OSError):
        return None
    return path if path.is_file() else None


@notebook_app.command("starter")
def notebook_starter(
    name: Annotated[
        str,
        typer.Argument(help="starter | ray_train | marimo"),
    ] = "starter",
    dest: Annotated[
        Path | None,
        typer.Option("--to", help="Destination directory (default: scratch/work)."),
    ] = None,
) -> None:
    """Copy a starter notebook into scratch/work.

    Examples:
        astroai-lab notebook starter
        astroai-lab notebook starter ray_train --to /scratch
        astroai-lab notebook starter marimo
    """
    filename = _STARTERS.get(name)
    if filename is None:
        known = ", ".join(sorted(_STARTERS))
        ui.print_error(f"Unknown starter {name!r}. Choose one of: {known}")
        raise typer.Exit(1)

    paths = resolve_paths()
    if dest is not None:
        target_dir = dest
    elif name == "marimo":
        target_dir = paths.work_dir / "notebooks"
    else:
        target_dir = paths.scratch_dir or paths.work_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    src = _resolve_starter(filename)
    if src is None:
        ui.print_error(f"Starter not found: {filename}")
        ui.print_hint("Expected under /opt/astroai/notebooks/ in AstroAI images.")
        raise typer.Exit(1)
    out = target_dir / filename
    shutil.copy2(src, out)
    ui.print_ok(f"Wrote {out}")
    if name == "marimo":
        ui.print_hint(
            "Opens by default in the marimo session (TMP_SRC_DIR/notebooks/starter.py). "
            "Existing projects: File → Open under TMP_SRC_DIR."
        )
    else:
        ui.print_hint(
            "Open it in Jupyter and select the AstroAI kernel (`astroai-lab kernel ensure`)."
        )
