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

ray_app = typer.Typer(help="Batch compute on CANFAR (Ray under the hood).")

from astroai_lab.cli.ray_ensure import (
    DEFAULT_WORKER_GPU,
    DEFAULT_WORKERS,
    ensure_compute,
    wire_orx,
    jobs_url_from_connect,
    read_persisted_connect_url,
    find_manager_sessions,
    canfar_sessions,
    _session_connect_url,
    _session_status,
)

RAY_GUIDE = """
[bold]Batch compute on AstroAI (CANFAR)[/bold]

[bold]One-click (recommended)[/bold]
  OpenResearch / OpenWorker → AstroAI hub → [bold]Start batch compute[/bold]
  or:
  astroai-lab ray ensure

That launches a manager session, starts workers, and wires OpenResearch to use
it automatically (`orx exp run` with no --backend once defaulted).

[bold]Manual[/bold]
  canfar create --name astroai-compute contributed images.canfar.net/astroai/ray-manager:<tag>
  Open Connect URL → preflight → create cluster
  Dashboard: connectURL/dashboard/

[bold]Submit Jobs[/bold]
  From OpenResearch: just run experiments (default compute = CANFAR batch).
  CLI: astroai-workload run train.py --cpus 2

[bold]Storage[/bold]
  /scratch is private to each pod — put shared I/O on /arc.

[bold]Docs[/bold]
  https://github.com/astroai/astroai-containers/blob/main/docs/RAY.md
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
    connect = root / "connect-url"
    if connect.is_file():
        try:
            entry["connect_url"] = connect.read_text(encoding="utf-8").strip()
        except OSError:
            pass
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
    managers = find_manager_sessions(canfar_sessions())
    running_mgr = next(
        (m for m in managers if _session_status(m) == "Running" and _session_connect_url(m)),
        None,
    )
    jobs_from_mgr = (
        jobs_url_from_connect(_session_connect_url(running_mgr)) if running_mgr else None
    )
    persisted = read_persisted_connect_url()
    jobs_from_persisted = jobs_url_from_connect(persisted) if persisted else None
    payload: dict[str, Any] = {
        "cluster_id": (primary or {}).get("cluster_id") or preferred,
        "state_dir": (primary or {}).get("state_dir"),
        "heartbeat_path": (primary or {}).get("heartbeat_path"),
        "heartbeat_present": bool((primary or {}).get("heartbeat_present")),
        "heartbeat_age_seconds": (primary or {}).get("heartbeat_age_seconds"),
        "state": (primary or {}).get("state"),
        "phase": (primary or {}).get("phase"),
        "clusters": clusters,
        "ray_address": (
            os.environ.get("ASTROAI_RAY_JOBS_ADDRESS")
            or os.environ.get("RAY_ADDRESS")
            or jobs_from_mgr
            or jobs_from_persisted
        ),
        "connect_url": (running_mgr and _session_connect_url(running_mgr))
        or (primary or {}).get("connect_url")
        or persisted,
        "manager_sessions": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "status": m.get("status"),
                "connectURL": _session_connect_url(m),
            }
            for m in managers
        ],
        "ray_image_tag": tag,
        "ray_version_expected": os.environ.get("RAY_VERSION_EXPECTED"),
        "launch_command": "astroai-lab ray ensure",
        "scratch_note": (
            "/scratch is private to each pod — put shared Jobs I/O on /arc/home or /arc/projects."
        ),
    }
    if primary and primary.get("state_error"):
        payload["state_error"] = primary["state_error"]
    if not any(c.get("heartbeat_present") for c in clusters) and not running_mgr:
        payload["hint"] = (
            "No batch-compute manager yet — run `astroai-lab ray ensure` "
            "or use Start batch compute in the AstroAI hub."
        )
    # Ready for OpenResearch when we have a Jobs address we can name.
    payload["compute_ready"] = bool(payload.get("ray_address") or payload.get("connect_url"))
    return payload


@ray_app.command("guide")
def ray_guide() -> None:
    """Print batch-compute launch cheat sheet for CANFAR."""
    console.print(RAY_GUIDE)


@ray_app.command("status")
def ray_status(
    ctx: typer.Context,
    state_dir: Annotated[
        Path | None,
        typer.Option("--state-dir", help="Cluster state directory override."),
    ] = None,
) -> None:
    """Show batch-compute / Ray manager status from shared home heartbeats.

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
    if payload.get("connect_url"):
        ui.print_info(f"manager: {payload['connect_url']}")
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
    ui.print_hint(f"ensure: {payload['launch_command']}")


@ray_app.command("ensure")
def ray_ensure_cmd(
    ctx: typer.Context,
    workers: Annotated[
        int,
        typer.Option("--workers", help="Headless workers to start (0 = manager only)."),
    ] = DEFAULT_WORKERS,
    gpus: Annotated[
        int,
        typer.Option("--gpus", help="GPUs per worker."),
    ] = DEFAULT_WORKER_GPU,
    skip_preflight: Annotated[
        bool,
        typer.Option("--skip-preflight", help="Skip network preflight (workers may not join)."),
    ] = False,
    no_create: Annotated[
        bool,
        typer.Option("--no-create", help="Do not create a manager; only reuse/wire."),
    ] = False,
    no_wire: Annotated[
        bool,
        typer.Option("--no-wire", help="Do not write OpenResearch Ray settings."),
    ] = False,
) -> None:
    """Start batch compute and wire OpenResearch to use it.

    Creates a ray-manager CANFAR session if needed, starts workers (best effort),
    and sets OpenResearch default compute to ``ray`` against that Jobs URL.
    """
    opts = get_opts(ctx)
    try:
        payload = ensure_compute(
            workers=workers,
            worker_gpus=gpus,
            skip_preflight=skip_preflight,
            create_manager=not no_create,
            wire=not no_wire,
        )
    except Exception as exc:  # noqa: BLE001
        if opts.json:
            ui.print_json({"ok": False, "error": str(exc)})
        else:
            ui.print_error(str(exc))
        raise typer.Exit(1) from exc

    if opts.json:
        ui.print_json(payload)
        return

    if payload.get("user_message"):
        if payload.get("ok"):
            ui.print_ok(str(payload["user_message"]))
        else:
            ui.print_hint(str(payload["user_message"]))
    if payload.get("jobs_address"):
        ui.print_info(f"jobs_api: {payload['jobs_address']}")
    if payload.get("manager", {}).get("connectURL"):
        ui.print_info(f"manager: {payload['manager']['connectURL']}")
    if not payload.get("ok"):
        raise typer.Exit(1)


@ray_app.command("wire-orx")
def ray_wire_orx(
    ctx: typer.Context,
    address: Annotated[
        str | None,
        typer.Option("--address", help="Jobs / Dashboard base URL override."),
    ] = None,
) -> None:
    """Write OpenResearch Ray settings from the current manager (or --address)."""
    opts = get_opts(ctx)
    jobs = (address or "").strip().rstrip("/")
    if not jobs:
        connect = read_persisted_connect_url()
        if not connect:
            managers = find_manager_sessions(canfar_sessions())
            running = [
                m for m in managers if _session_status(m) == "Running" and _session_connect_url(m)
            ]
            if running:
                connect = _session_connect_url(running[0])
        if not connect:
            ui.print_error("No manager URL found — pass --address or run ray ensure first")
            raise typer.Exit(1)
        jobs = jobs_url_from_connect(connect)
    payload = wire_orx(jobs_address=jobs, make_default=True)
    if opts.json:
        ui.print_json(payload)
        return
    ui.print_ok(f"OpenResearch default compute → ray ({payload['address']})")
