"""Ray cluster helpers for CANFAR AstroAI sessions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Annotated, Any

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


def _cluster_roots(home: Path, *, state_dir: Path | None) -> list[Path]:
    if state_dir is not None:
        return [state_dir]
    clusters = home / ".astroai" / "ray" / "clusters"
    if not clusters.is_dir():
        preferred = os.environ.get("RAY_CLUSTER_ID", "").strip() or "default"
        return [clusters / preferred]
    roots = sorted(p for p in clusters.iterdir() if p.is_dir())
    return roots or [clusters / (os.environ.get("RAY_CLUSTER_ID", "").strip() or "default")]


def _read_cluster(root: Path) -> dict[str, Any]:
    heartbeat = root / "manager-heartbeat"
    state_file = root / "state.json"
    entry: dict[str, Any] = {
        "cluster_id": root.name,
        "state_dir": str(root),
        "heartbeat_path": str(heartbeat),
        "heartbeat_present": heartbeat.is_file(),
        "heartbeat_age_seconds": None,
        "phase": None,
        "state": None,
    }
    if heartbeat.is_file():
        try:
            entry["heartbeat_age_seconds"] = int(time.time() - heartbeat.stat().st_mtime)
        except OSError:
            entry["heartbeat_age_seconds"] = None
    if state_file.is_file():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            entry["state"] = state
            if isinstance(state, dict):
                entry["phase"] = state.get("phase") or state.get("status")
        except (OSError, json.JSONDecodeError) as exc:
            entry["state_error"] = str(exc)
    return entry


def collect_ray_status(*, state_dir: Path | None = None) -> dict[str, Any]:
    """Build Ray status payload (used by CLI and the AstroAI hub)."""
    home = Path(os.environ.get("HOME") or Path.home())
    preferred = os.environ.get("RAY_CLUSTER_ID", "").strip() or "default"
    roots = _cluster_roots(home, state_dir=state_dir)
    clusters = [_read_cluster(root) for root in roots]
    # Prefer env cluster id, else freshest heartbeat, else first entry.
    primary = None
    for c in clusters:
        if c["cluster_id"] == preferred:
            primary = c
            break
    if primary is None:
        with_hb = [c for c in clusters if c.get("heartbeat_present")]
        if with_hb:
            primary = min(
                with_hb,
                key=lambda c: c.get("heartbeat_age_seconds")
                if c.get("heartbeat_age_seconds") is not None
                else 10**9,
            )
        elif clusters:
            primary = clusters[0]

    tag = os.environ.get("RAY_IMAGE_TAG") or os.environ.get("BUILD_TAG") or "26.07"
    payload: dict[str, Any] = {
        "cluster_id": (primary or {}).get("cluster_id") or preferred,
        "state_dir": (primary or {}).get("state_dir"),
        "heartbeat_path": (primary or {}).get("heartbeat_path"),
        "heartbeat_present": bool((primary or {}).get("heartbeat_present")),
        "heartbeat_age_seconds": (primary or {}).get("heartbeat_age_seconds"),
        "state": (primary or {}).get("state"),
        "phase": (primary or {}).get("phase"),
        "clusters": clusters,
        "ray_address": os.environ.get("ASTROAI_RAY_JOBS_ADDRESS")
        or os.environ.get("RAY_ADDRESS"),
        "ray_image_tag": tag,
        "ray_version_expected": os.environ.get("RAY_VERSION_EXPECTED"),
        "launch_command": (
            "canfar create --name raymgr --cpu 2 --memory 8 contributed "
            f"images.canfar.net/astroai/ray-manager:{tag}"
        ),
        "scratch_note": (
            "/scratch is private to each pod — put shared Jobs I/O on /arc/home or /arc/projects."
        ),
    }
    if primary and primary.get("state_error"):
        payload["state_error"] = primary["state_error"]
    if not any(c.get("heartbeat_present") for c in clusters):
        payload["hint"] = (
            "No manager heartbeat under ~/.astroai/ray/clusters/ — "
            "launch ray-manager (Portal or launch_command) to create a cluster."
        )
    return payload


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
    """Show Ray manager cluster status from shared home heartbeats.

    Scans ``~/.astroai/ray/clusters/*/`` so openresearch/openworker sessions can
    see a manager started in another session on the same ``/arc/home``.

    Examples:
        astroai-lab ray status
        astroai-lab ray status --json
    """
    opts = get_opts(ctx)
    payload = collect_ray_status(state_dir=state_dir)

    if opts.json:
        ui.print_json(payload)
        return

    ui.print_info(f"cluster: {payload['cluster_id']}")
    ui.print_info(f"state_dir: {payload.get('state_dir')}")
    ui.print_info(f"heartbeat: {'yes' if payload.get('heartbeat_present') else 'no'}")
    if payload.get("heartbeat_age_seconds") is not None:
        ui.print_info(f"heartbeat_age: {payload['heartbeat_age_seconds']}s")
    if payload.get("phase"):
        ui.print_info(f"phase: {payload['phase']}")
    if payload.get("ray_address"):
        ui.print_info(f"jobs_api: {payload['ray_address']}")
    if payload.get("ray_image_tag"):
        ui.print_info(f"image_tag: {payload['ray_image_tag']}")
    others = [
        c
        for c in (payload.get("clusters") or [])
        if c.get("cluster_id") != payload.get("cluster_id") and c.get("heartbeat_present")
    ]
    if others:
        ui.print_info(
            "other_clusters: "
            + ", ".join(
                f"{c['cluster_id']} (age {c.get('heartbeat_age_seconds')}s)" for c in others
            )
        )
    if payload.get("hint"):
        ui.print_hint(str(payload["hint"]))
    ui.print_hint(f"launch: {payload['launch_command']}")
