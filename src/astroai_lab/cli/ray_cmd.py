"""Ray cluster helpers for CANFAR AstroAI sessions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import get_opts
from astroai_lab.utils.console import console

ray_app = typer.Typer(help="Ray on CANFAR — status and launch cheat sheet.")

RAY_GUIDE = """
[bold]Ray on AstroAI (CANFAR)[/bold]

[bold]Launch manager[/bold]
  Portal → ray-manager
  or:
  canfar create --name raymgr contributed images.canfar.net/astroai/ray-manager:<tag>

[bold]Inside the manager session[/bold]
  Open Connect URL → control panel at /
  Dashboard: connectURL/dashboard/
  astroai-lab ray status

[bold]Workers[/bold]
  Manager launches headless ray-worker images (do not register workers in the portal).
  Optional env restore on workers: ASTROAI_LAB_RESUME=<save>
  Saves live on /arc (e.g. ~/.astroai/lab/saves or /arc/projects/<group>/env-saves).

[bold]Storage[/bold]
  /scratch is private to each pod — not shared across manager/workers/interactive sessions.
  Put shared code/data/env saves on /arc/home or /arc/projects.

[bold]Resources[/bold]
  Manager memory ≥8 GiB recommended (Jobs + Dashboard).
  Docs: https://github.com/astroai/astroai-containers/blob/main/docs/RAY.md
"""


@ray_app.command("guide")
def ray_guide() -> None:
    """Print Ray launch cheat sheet for CANFAR."""
    console.print(RAY_GUIDE)


@ray_app.command("status")
def ray_status(
    ctx: typer.Context,
    state_dir: Annotated[
        Path | None,
        typer.Option("--state-dir", help="Cluster state directory override."),
    ] = None,
) -> None:
    """Show local Ray manager cluster status if this looks like a manager session.

    Examples:
        astroai-lab ray status
        astroai-lab ray status --json
    """
    opts = get_opts(ctx)
    cluster_id = os.environ.get("RAY_CLUSTER_ID", "").strip() or "default"
    home = Path(os.environ.get("HOME") or Path.home())
    root = state_dir or (home / ".astroai" / "ray" / "clusters" / cluster_id)
    heartbeat = root / "manager-heartbeat"
    state_file = root / "state.json"

    payload: dict[str, object] = {
        "cluster_id": cluster_id,
        "state_dir": str(root),
        "heartbeat_path": str(heartbeat),
        "heartbeat_present": heartbeat.is_file(),
        "ray_address": os.environ.get("ASTROAI_RAY_JOBS_ADDRESS")
        or os.environ.get("RAY_ADDRESS"),
        "ray_image_tag": os.environ.get("RAY_IMAGE_TAG") or os.environ.get("BUILD_TAG"),
        "ray_version_expected": os.environ.get("RAY_VERSION_EXPECTED"),
    }

    if heartbeat.is_file():
        try:
            age = int(__import__("time").time() - heartbeat.stat().st_mtime)
            payload["heartbeat_age_seconds"] = age
        except OSError:
            payload["heartbeat_age_seconds"] = None

    if state_file.is_file():
        try:
            payload["state"] = json.loads(state_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            payload["state_error"] = str(exc)
    else:
        payload["state"] = None
        payload["hint"] = (
            "No cluster state file — launch ray-manager or open its UI to create a cluster."
        )

    if opts.json:
        ui.print_json(payload)
        return

    ui.print_info(f"cluster: {payload['cluster_id']}")
    ui.print_info(f"state_dir: {payload['state_dir']}")
    ui.print_info(f"heartbeat: {'yes' if payload['heartbeat_present'] else 'no'}")
    if "heartbeat_age_seconds" in payload and payload["heartbeat_age_seconds"] is not None:
        ui.print_info(f"heartbeat_age: {payload['heartbeat_age_seconds']}s")
    if payload.get("ray_address"):
        ui.print_info(f"jobs_api: {payload['ray_address']}")
    if payload.get("ray_image_tag"):
        ui.print_info(f"image_tag: {payload['ray_image_tag']}")
    if payload.get("hint"):
        ui.print_hint(str(payload["hint"]))
    elif isinstance(payload.get("state"), dict):
        phase = payload["state"].get("phase") or payload["state"].get("status")
        if phase:
            ui.print_info(f"phase: {phase}")
