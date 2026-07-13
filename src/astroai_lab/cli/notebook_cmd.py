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


@notebook_app.command("starter")
def notebook_starter(
    name: Annotated[str, typer.Argument(help="starter | ray_train")] = "starter",
    dest: Annotated[
        Path | None,
        typer.Option("--to", help="Destination directory (default: scratch or work)."),
    ] = None,
) -> None:
    """Copy a starter notebook into scratch/work.

    Examples:
        astroai-lab notebook starter
        astroai-lab notebook starter ray_train --to /scratch
    """
    paths = resolve_paths()
    target_dir = dest or paths.scratch_dir or paths.work_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = "starter.ipynb" if name == "starter" else f"{name}.ipynb"
    src = _IMAGE_STARTERS / filename
    if not src.is_file():
        # Bundled fallback inside the package (minimal).
        try:
            pkg = importlib.resources.files("astroai_lab.data") / "notebooks" / filename
            src = Path(str(pkg))
        except Exception:
            src = Path()
    if not src.is_file():
        ui.print_error(f"Starter not found: {filename}")
        ui.print_hint("Expected under /opt/astroai/notebooks/ in AstroAI images.")
        raise typer.Exit(1)
    out = target_dir / filename
    shutil.copy2(src, out)
    ui.print_ok(f"Wrote {out}")
    ui.print_hint("Open it in Jupyter and select the AstroAI kernel (`astroai-lab kernel ensure`).")
