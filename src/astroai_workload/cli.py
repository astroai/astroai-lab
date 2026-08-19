"""Run programs on a CANFAR Ray cluster, or start and resize that cluster."""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from .executor import RayExecutor, run_script
from .models import DataProductRef, ResourceRequest, RunSpec, RunStatus

_MAIN_HELP = """
Run a program on a Ray cluster, or start/resize the workers that cluster uses.

  Autoscaling (usual path)
    astroai cluster start --autoscaling
    astroai run train.py --cpus 2

  Fixed-size workers
    astroai cluster start --workers 2
    astroai cluster scale 0          # stop workers, keep the manager

  Jobs (cluster already up)
    astroai run train.py --cpus 2
    astroai jobs submit --cmd 'python -m mosaic.stack' --wait
"""

app = typer.Typer(
    name="astroai",
    help=_MAIN_HELP.strip(),
    no_args_is_help=True,
    add_completion=False,
)

cluster_app = typer.Typer(
    name="cluster",
    help=(
        "Start a ray-manager and workers. "
        "`start --autoscaling` is the usual path (Ray adds workers when jobs need CPUs). "
        "`start --workers N` starts a fixed pool instead. "
        "`check` shows whether it is up."
    ),
    no_args_is_help=True,
    add_completion=False,
)
dashboard_app = typer.Typer(
    name="dashboard",
    help="Ray Dashboard URL (jobs, nodes, logs). No subcommand prints the URL.",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
)
autoscaler_app = typer.Typer(
    name="autoscaler",
    help=(
        "Write YAML so the Ray head starts and stops CANFAR workers on demand. "
        "This is the manager-head path, not `run`. Most people should "
        "`cluster start --autoscaling` instead."
    ),
    no_args_is_help=True,
    add_completion=False,
)
mcp_app = typer.Typer(
    name="mcp",
    help="Stdio tools for agents: cluster start/check/scale plus job run/list/status/logs/cancel.",
    no_args_is_help=True,
    add_completion=False,
)
cluster_app.add_typer(dashboard_app)
app.add_typer(cluster_app)
app.add_typer(dashboard_app, hidden=True)
app.add_typer(autoscaler_app, hidden=True)
app.add_typer(mcp_app, hidden=True)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _warn_renamed(ctx: typer.Context, new: str) -> None:
    invoked = ctx.info_name
    if invoked and invoked != new:
        print(
            f"warning: `astroai cluster {invoked}` is now `astroai cluster {new}`",
            file=sys.stderr,
        )


def _manager_base_url(address: str | None) -> str:
    """Derive the manager base URL (connect URL) from the Jobs address.

    Inside the manager pod the Jobs address is ``http://127.0.0.1:8265`` and the
    manager UI is ``http://127.0.0.1:5000``. From another session it is the
    public connect URL with ``/dashboard`` stripped off (Jobs lives under the
    dashboard proxy).
    """
    resolved = (address or "").strip().rstrip("/")
    if not resolved:
        from .dashboard import resolve_dashboard_url

        resolved = resolve_dashboard_url() or ""
        if not resolved:
            raise typer.BadParameter(
                "No Ray manager address. Run `astroai cluster start` first, "
                "or set ASTROAI_RAY_JOBS_ADDRESS / pass --address."
            )
    if resolved.endswith("/dashboard"):
        return resolved[: -len("/dashboard")]
    if "127.0.0.1" in resolved or "localhost" in resolved:
        port = resolved.rsplit(":", 1)[-1]
        return f"http://127.0.0.1:{5000 if port == '8265' else port}"
    return resolved


def _manager_client(address: str | None) -> Any:
    from .manager_client import ManagerClient

    return ManagerClient(_manager_base_url(address))


def _cluster_payload_from(address: str | None) -> dict[str, Any]:
    client = _manager_client(address)
    return client.status()


def _parse_env(items: list[str] | None) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for item in items or ():
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        env_map[key] = value
    return env_map


def _uri_refs(uris: list[str] | None) -> tuple[DataProductRef, ...]:
    return tuple(DataProductRef(uri) for uri in uris or ())


def _resources(cpus: float, gpus: float, memory: str | None) -> ResourceRequest:
    if memory is not None:
        return ResourceRequest(cpus=cpus, gpus=gpus, memory=memory)
    return ResourceRequest(cpus=cpus, gpus=gpus)


def job_run_payload(
    script: str,
    *,
    address: str | None = None,
    cpus: float = 1.0,
    memory: str | None = None,
    gpus: float = 0.0,
    args: list[str] | None = None,
    env: list[str] | None = None,
    timeout: float | None = None,
    working_directory: str | None = None,
    run_id: str | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> dict[str, Any]:
    """Run a Python script on the cluster and wait. Shared by CLI and MCP."""
    rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
    status, logs = run_script(
        script,
        address=address,
        cpus=cpus,
        memory=memory,
        gpus=gpus,
        args=args,
        env=_parse_env(env) or None,
        timeout=timeout,
        working_directory=working_directory,
        run_id=rid,
        inputs=inputs,
        expected_outputs=outputs,
    )
    return {"run_id": rid, "status": status.value, "logs": logs}


def job_submit_payload(
    command: tuple[str, ...],
    *,
    address: str | None = None,
    cpus: float = 1.0,
    memory: str | None = None,
    gpus: float = 0.0,
    env: list[str] | None = None,
    timeout: float | None = None,
    working_directory: str | None = None,
    run_id: str | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    wait: bool = False,
) -> dict[str, Any]:
    """Submit a command to the cluster. Shared by CLI and MCP."""
    rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
    spec = RunSpec(
        run_id=rid,
        command=command,
        resources=_resources(cpus, gpus, memory),
        environment=_parse_env(env),
        working_directory=working_directory,
        inputs=_uri_refs(inputs),
        expected_outputs=_uri_refs(outputs),
    )
    ex = RayExecutor(address=address)
    if wait:
        status, logs = ex.submit_and_wait(spec, timeout=timeout)
        return {"run_id": rid, "status": status.value, "logs": logs}
    return {"run_id": ex.submit(spec)}


def job_status_payload(run_id: str, address: str | None = None) -> dict[str, Any]:
    status = RayExecutor(address=address).status(run_id)
    return {"run_id": run_id, "status": status.value}


def job_logs_payload(run_id: str, address: str | None = None) -> dict[str, Any]:
    return {"run_id": run_id, "logs": RayExecutor(address=address).logs(run_id)}


def job_wait_payload(
    run_id: str,
    *,
    address: str | None = None,
    timeout: float | None = None,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    status, logs = RayExecutor(address=address).wait(
        run_id, poll_interval=poll_interval, timeout=timeout
    )
    return {"run_id": run_id, "status": status.value, "logs": logs}


def job_cancel_payload(run_id: str, address: str | None = None) -> dict[str, Any]:
    RayExecutor(address=address).cancel(run_id)
    return {"run_id": run_id, "cancel": "requested"}


def job_list_payload(address: str | None = None) -> dict[str, Any]:
    return {"jobs": RayExecutor(address=address).list_jobs()}


def _cli_fail(exc: BaseException) -> NoReturn:
    print(str(exc), file=sys.stderr)
    raise typer.Exit(1)


# =====================================================================
# Jobs commands (cluster must already be up)
# =====================================================================


@app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def cmd_run(
    ctx: typer.Context,
    script: Annotated[Path, typer.Argument(help="Python script to run on the cluster.")],
    cpus: Annotated[float, typer.Option("--cpus", help="CPUs for the driver process.")] = 1.0,
    memory: Annotated[
        str | None,
        typer.Option(
            "--memory",
            "-m",
            help="RAM for the driver (for example 8GiB). Omit unless that RAM is free.",
        ),
    ] = None,
    gpus: Annotated[float, typer.Option("--gpus", help="GPUs for the driver process.")] = 0.0,
    address: Annotated[
        str | None,
        typer.Option("--address", help="Cluster URL (default: ASTROAI_RAY_JOBS_ADDRESS)."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Seconds to wait (default: until the job ends)."),
    ] = None,
    working_directory: Annotated[
        Path | None,
        typer.Option("--cwd", help="Job working directory (default: script folder)."),
    ] = None,
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="Name for this job (default: random)."),
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option("--env", help="Environment KEY=VALUE (repeat)."),
    ] = None,
    inputs: Annotated[
        list[str] | None,
        typer.Option("--input", help="URI this job reads (repeat). Stored on the Ray job."),
    ] = None,
    outputs: Annotated[
        list[str] | None,
        typer.Option("--output", help="URI this job writes (repeat). Stored on the Ray job."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Run a Python script on the Ray cluster and wait until it finishes.

    Does not start workers. Use `cluster start` first.

    Extra arguments after the script go to the script
    (`astroai run train.py --epochs 2`).

    Examples:
      astroai run train.py --cpus 2
      astroai run train.py --gpus 1 --input /arc/projects/g/in --output /arc/projects/g/out
    """
    try:
        result = job_run_payload(
            str(script),
            address=address,
            cpus=cpus,
            memory=memory,
            gpus=gpus,
            args=list(ctx.args),
            env=env,
            timeout=timeout,
            working_directory=str(working_directory) if working_directory else None,
            run_id=run_id,
            inputs=inputs,
            outputs=outputs,
        )
    except (ValueError, FileNotFoundError, RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    if as_json:
        _print_json(result)
    else:
        print(f"run_id: {result['run_id']}", file=sys.stderr)
        print(f"status: {result['status']}", file=sys.stderr)
        logs = result.get("logs") or ""
        if logs:
            print(logs, end="" if str(logs).endswith("\n") else "\n")
    raise typer.Exit(0 if result["status"] == RunStatus.SUCCEEDED.value else 1)


@app.command("submit")
def cmd_submit(
    cmd: Annotated[
        str | None,
        typer.Option("--cmd", help="Command to run on the cluster, as one string."),
    ] = None,
    argv: Annotated[
        list[str] | None,
        typer.Argument(help="Command words when --cmd is omitted."),
    ] = None,
    cpus: Annotated[float, typer.Option("--cpus")] = 1.0,
    memory: Annotated[
        str | None,
        typer.Option(
            "--memory",
            "-m",
            help="RAM for the driver (for example 8GiB). Omit unless that RAM is free.",
        ),
    ] = None,
    gpus: Annotated[float, typer.Option("--gpus")] = 0.0,
    address: Annotated[str | None, typer.Option("--address")] = None,
    working_directory: Annotated[Path | None, typer.Option("--cwd")] = None,
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    env: Annotated[list[str] | None, typer.Option("--env")] = None,
    inputs: Annotated[
        list[str] | None,
        typer.Option("--input", help="URI this job reads (repeat). Stored on the Ray job."),
    ] = None,
    outputs: Annotated[
        list[str] | None,
        typer.Option("--output", help="URI this job writes (repeat). Stored on the Ray job."),
    ] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Wait until the job finishes.")] = False,
    timeout: Annotated[float | None, typer.Option("--timeout")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Start a command on the Ray cluster without requiring a .py file.

    Same cluster as `run`. Use this for `python -m package` and other commands.
    Does not wait unless you pass --wait.

    Examples:
      astroai jobs submit --cmd 'python -m mosaic.stack --in /arc/projects/g/in'
      astroai jobs submit --cmd 'python train.py' --wait --cpus 2
    """
    if cmd:
        command = tuple(shlex.split(cmd))
    elif argv:
        command = tuple(argv)
    else:
        raise typer.BadParameter("pass --cmd '…' or the command words", param_hint="--cmd")
    try:
        result = job_submit_payload(
            command,
            address=address,
            cpus=cpus,
            memory=memory,
            gpus=gpus,
            env=env,
            timeout=timeout,
            working_directory=str(working_directory) if working_directory else None,
            run_id=run_id,
            inputs=inputs,
            outputs=outputs,
            wait=wait,
        )
    except (ValueError, RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    if as_json:
        _print_json(result)
        if wait:
            raise typer.Exit(0 if result.get("status") == RunStatus.SUCCEEDED.value else 1)
        return
    if wait:
        print(result["run_id"])
        print(f"status: {result['status']}", file=sys.stderr)
        logs = result.get("logs") or ""
        if logs:
            print(logs, end="" if str(logs).endswith("\n") else "\n")
        raise typer.Exit(0 if result["status"] == RunStatus.SUCCEEDED.value else 1)
    print(result["run_id"])


@app.command("status")
def cmd_status(
    run_id: Annotated[str, typer.Argument(help="Job id from run/submit.")],
    address: Annotated[str | None, typer.Option("--address")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show whether one job is still running, succeeded, or failed."""
    try:
        result = job_status_payload(run_id, address)
    except (RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    if as_json:
        _print_json(result)
    else:
        print(result["status"])


@app.command("logs")
def cmd_logs(
    run_id: Annotated[str, typer.Argument(help="Job id from run/submit.")],
    address: Annotated[str | None, typer.Option("--address")] = None,
) -> None:
    """Print the driver log for one job."""
    try:
        result = job_logs_payload(run_id, address)
    except (RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    logs = result["logs"]
    print(logs, end="" if str(logs).endswith("\n") else "\n")


@app.command("wait")
def cmd_wait(
    run_id: Annotated[str, typer.Argument(help="Job id from run/submit.")],
    address: Annotated[str | None, typer.Option("--address")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout")] = None,
    poll_interval: Annotated[float, typer.Option("--poll-interval")] = 2.0,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Wait until a job finishes, then print its log."""
    try:
        result = job_wait_payload(
            run_id, address=address, timeout=timeout, poll_interval=poll_interval
        )
    except (RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    if as_json:
        _print_json(result)
    else:
        print(f"status: {result['status']}", file=sys.stderr)
        logs = result.get("logs") or ""
        if logs:
            print(logs, end="" if str(logs).endswith("\n") else "\n")
    raise typer.Exit(0 if result["status"] == RunStatus.SUCCEEDED.value else 1)


@app.command("cancel")
def cmd_cancel(
    run_id: Annotated[str, typer.Argument(help="Job id from run/submit.")],
    address: Annotated[str | None, typer.Option("--address")] = None,
) -> None:
    """Ask the cluster to stop a job."""
    try:
        result = job_cancel_payload(run_id, address)
    except (RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    print(f"cancel requested: {result['run_id']}")


@app.command("list")
def cmd_list(
    address: Annotated[str | None, typer.Option("--address")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List jobs on the current cluster."""
    try:
        result = job_list_payload(address)
    except (RuntimeError, ConnectionError, OSError) as exc:
        _cli_fail(exc)
    jobs = result["jobs"]
    if as_json:
        _print_json(jobs)
        return
    if not jobs:
        print("No jobs.")
        return
    print(f"{'RUN ID':<24} {'STATUS':<12} COMMAND")
    for job in jobs:
        rid = str(job.get("submission_id") or job.get("job_id") or "-")
        status = str(job.get("status") or "-")
        entry = str(job.get("entrypoint") or "")
        print(f"{rid:<24} {status:<12} {entry}")


# =====================================================================
# Cluster lifecycle commands (manager /api/v1)
# =====================================================================


def _manager_image() -> str:
    explicit = os.environ.get("RAY_MANAGER_IMAGE", "").strip()
    if explicit:
        return explicit
    tag = os.environ.get("RAY_IMAGE_TAG", os.environ.get("BUILD_TAG", "latest"))
    registry = os.environ.get("REGISTRY", "images.canfar.net")
    owner = os.environ.get("OWNER", "astroai")
    return f"{registry}/{owner}/ray-manager:{tag}"


def cluster_ensure_payload(
    *,
    address: str | None = None,
    workers: int = 0,
    cores: int = 1,
    ram: int = 4,
    gpus: int = 0,
    timeout: int = 1800,
    require_preflight: bool = False,
    autoscaling: bool = False,
    max_workers: int = 8,
) -> dict[str, Any]:
    """Ensure a ray-manager is running; optionally launch workers.

    Single source of truth shared by ``astroai cluster start`` and the
    MCP ``cluster_start`` tool. Resolves the manager (env → persisted connect
    URL → ``canfar ps`` discovery), waits for /readyz, optionally creates
    workers, and returns the Jobs address + Dashboard URL as a JSON-safe dict.

    ``autoscaling=True`` writes ``~/.config/canfar/lab/ray-manager.env`` and
    creates the manager if needed. It does not launch a fixed worker pool.
    Ray starts ``ray-as-*`` workers when a job needs CPUs.

    ``require_preflight`` defaults to False: on some Skaha deployments the
    headless preflight probe never leaves Pending (known platform quirk), which
    would otherwise block worker creation for agent one-click flows. Agents can
    pass ``require_preflight=True`` to enforce the network preflight gate.

    Raises RuntimeError with a human-readable message when no manager can be
    resolved or the manager is not ready.
    """
    from .dashboard import persist_connect_url, resolve_dashboard_url

    existing_manager = False
    if autoscaling:
        from .autoscaler import write_manager_autoscaling_env

        write_manager_autoscaling_env(
            min_workers=workers,
            max_workers=max_workers,
            cores=cores,
            ram_gb=ram,
            gpus=gpus,
        )
        workers = 0
        if not address:
            try:
                from .canfar_ops import CanfarOps
            except ImportError as exc:
                raise RuntimeError("The canfar client is required to create a manager.") from exc

            ops = CanfarOps()
            existing_manager = ops.find_manager() is not None
            if not existing_manager:
                ops.create_contributed(
                    name="raymgr",
                    image=_manager_image(),
                    cores=2,
                    ram=8,
                )

    if address:
        base = address.rstrip("/")
    else:
        # Fresh manager is often Pending without a connect URL until the image
        # pull finishes. Poll for the full caller timeout (default 1800s), not
        # a 2-minute cap — Harbor pulls commonly exceed that.
        poll_s = 5
        max_polls = max(1, timeout // poll_s) if timeout else 12
        base = ""
        for _ in range(max_polls):
            jobs = resolve_dashboard_url()
            base = (
                jobs[: -len("/dashboard")] if jobs and jobs.endswith("/dashboard") else jobs or ""
            )
            if base:
                break
            time.sleep(poll_s)
    if not base:
        raise RuntimeError(
            "No ray-manager found. Run `astroai cluster start --autoscaling` "
            "or start one from the AstroAI hub (Start batch compute)."
        )

    client = _manager_client(base)
    if not client.wait_ready(timeout_seconds=min(timeout, 600)):
        raise RuntimeError(f"Manager not ready at {base} (check auth / preflight).")

    manager_name = base.rstrip("/").rsplit("/", 1)[-1]
    persist_connect_url(manager_name or "default", base)

    created = None
    if workers > 0:
        payload = client.create_cluster(
            name=manager_name or "default",
            worker_count=workers,
            cores=cores,
            ram_gb=ram,
            gpus=gpus,
            require_preflight=require_preflight,
            async_mode=True,
        )
        created = payload
        if payload.get("accepted") or payload.get("cluster", {}).get("phase") == "Running":
            payload = client.wait_operation(timeout_seconds=timeout)

    status = client.status()
    jobs_url = base.rstrip("/") + "/dashboard"
    result: dict[str, Any] = {
        "manager_url": base,
        "jobs_address": jobs_url,
        "dashboard_url": jobs_url,
        "cluster_phase": (status.get("cluster") or {}).get("phase"),
        "joined_workers": status.get("joined_workers", 0),
        "worker_count": (status.get("cluster") or {}).get("worker_count"),
        "autoscaling": autoscaling,
    }
    if autoscaling and existing_manager:
        result["restart_manager"] = True
    if created is not None:
        result["create_accepted"] = created.get("accepted", False)
    return result


@cluster_app.command("start")
@cluster_app.command("ensure", hidden=True)
def cluster_cmd_start(
    ctx: typer.Context,
    address: Annotated[
        str | None,
        typer.Option("--address", help="Manager connect URL or Jobs API URL."),
    ] = None,
    workers: Annotated[int, typer.Option("--workers", help="Worker sessions to launch.")] = 0,
    cores: Annotated[int, typer.Option("--cores", help="CPUs per worker.")] = 1,
    ram: Annotated[int, typer.Option("--ram", help="RAM GiB per worker.")] = 4,
    gpus: Annotated[int, typer.Option("--gpus", help="GPUs per worker.")] = 0,
    timeout: Annotated[int, typer.Option("--timeout", help="Wait timeout (seconds).")] = 1800,
    require_preflight: Annotated[
        bool,
        typer.Option(
            "--require-preflight",
            help=(
                "Enforce the network preflight gate before launching workers. "
                "Off by default (Skaha headless probes can hang on some "
                "deployments); set it when the platform preflight works."
            ),
        ),
    ] = False,
    autoscaling: Annotated[
        bool,
        typer.Option(
            "--autoscaling",
            help="Usual path. Ray adds workers when a job needs CPUs. Creates the manager.",
        ),
    ] = False,
    max_workers: Annotated[
        int,
        typer.Option("--max-workers", help="Autoscaler ceiling (with --autoscaling)."),
    ] = 8,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Start the Ray cluster. Safe to run if one is already up.

    `--autoscaling` is the usual path: writes the manager env file, creates
    the manager if needed, and lets Ray add `ray-as-*` workers on demand.
    `--workers N` starts a fixed pool instead (does not create the manager).

    Examples:
      astroai cluster start --autoscaling
      astroai cluster start --workers 2
    """
    _warn_renamed(ctx, "start")
    try:
        result = cluster_ensure_payload(
            address=address,
            workers=workers,
            cores=cores,
            ram=ram,
            gpus=gpus,
            timeout=timeout,
            require_preflight=require_preflight,
            autoscaling=autoscaling,
            max_workers=max_workers,
        )
    except RuntimeError as exc:
        _cli_fail(exc)
    if as_json:
        _print_json(result)
    else:
        print(f"manager:     {result['manager_url']}")
        print(f"jobs/dash:   {result['jobs_address']}")
        print(f"phase:       {result['cluster_phase']}  joined: {result['joined_workers']}")
        if result.get("autoscaling"):
            print(f"autoscaling: on (max {max_workers} workers)")
        if result.get("restart_manager"):
            print(
                "this manager was already running — stop it and re-run "
                "`cluster start --autoscaling` if jobs do not scale"
            )
    # Hint for the caller's shell (a CLI cannot export into its parent).
    print(f"export ASTROAI_RAY_JOBS_ADDRESS={result['jobs_address']}")
    raise typer.Exit(0)


def cluster_status_payload(address: str | None = None) -> dict[str, Any]:
    """Cluster status payload (manager /api/v1/status) — CLI + MCP shared."""
    return _cluster_payload_from(address)


@cluster_app.command("check")
@cluster_app.command("status", hidden=True)
def cluster_cmd_check(
    ctx: typer.Context,
    address: Annotated[str | None, typer.Option("--address")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """See if the cluster is up, and get the Ray Dashboard URL."""
    _warn_renamed(ctx, "check")
    payload = cluster_status_payload(address)
    if as_json:
        _print_json(payload)
        return
    cluster = payload.get("cluster") or {}
    print(f"phase:        {cluster.get('phase', 'Idle')}")
    print(f"ray address:  {payload.get('ray_address')}")
    print(f"ray nodes:    {payload.get('ray_nodes_alive')}")
    print(f"joined:       {payload.get('joined_workers')} / {cluster.get('worker_count')}")
    auth = payload.get("auth") or {}
    print(f"auth:         {'ok' if auth.get('authenticated') else 'missing'}")
    print(f"dashboard:    {payload.get('dashboard_path')}")
    for w in payload.get("workers") or []:
        print(
            f"  worker {w.get('name')}: {w.get('phase')} joined={w.get('ray_joined')} "
            f"ip={w.get('worker_ip') or '-'}"
        )


@cluster_app.command("stop")
def cluster_cmd_stop(
    address: Annotated[str | None, typer.Option("--address")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Stop the cluster and destroy every worker session. Keeps the manager."""
    payload = _manager_client(address).stop_cluster()
    if as_json:
        _print_json(payload)
    else:
        cluster = payload.get("cluster") or {}
        print(f"cluster stopped (phase={cluster.get('phase')})")


def cluster_scale_payload(
    workers: int,
    *,
    address: str | None = None,
    cores: int = 1,
    ram: int = 4,
    gpus: int = 0,
    timeout: int = 1800,
    require_preflight: bool = False,
) -> dict[str, Any]:
    """Scale worker sessions up or down to *workers* — CLI + MCP shared.

    Launches new workers via the manager API when the cluster is smaller than
    the target, and destroys excess workers when larger. For true on-demand
    autoscaling, use `cluster start --autoscaling` instead of this command.

    ``require_preflight`` defaults to False to match ``cluster start`` (Skaha
    headless probes can hang). Pass True to enforce the network preflight gate.
    Returns a JSON-safe result dict.
    """
    from .state_store import TERMINAL_WORKER_PHASES

    client = _manager_client(address)
    status = client.status()
    workers_list = list(status.get("workers") or [])
    active = [
        w
        for w in workers_list
        if w.get("session_id") and w.get("phase") not in TERMINAL_WORKER_PHASES
    ]
    current = len(active) if active else int(status.get("joined_workers") or 0)
    target = max(0, workers)

    if target > current:
        need = target - current
        for _ in range(need):
            client.launch_worker(
                cores=cores, ram_gb=ram, gpus=gpus, require_preflight=require_preflight
            )
        result = client.wait_operation(timeout_seconds=timeout)
    elif target < current:
        extra = current - target
        destroyed = 0
        # Drop pending/unjoined first so a shrink does not kill healthy nodes
        # while leftover Pending sessions keep the count high.
        shrinkable = sorted(active, key=lambda w: (bool(w.get("ray_joined")), w.get("name") or ""))
        for w in shrinkable:
            if destroyed >= extra:
                break
            if w.get("session_id"):
                client.destroy_worker(w["session_id"])
                destroyed += 1
        result = client.wait_operation(timeout_seconds=timeout)
    else:
        result = status

    return {
        "target": target,
        "previous": current,
        "phase": (result.get("cluster") or {}).get("phase"),
        "joined_workers": result.get("joined_workers", 0),
    }


@cluster_app.command("scale")
def cluster_cmd_scale(
    workers: Annotated[int, typer.Argument(help="Target number of worker sessions.")],
    address: Annotated[str | None, typer.Option("--address")] = None,
    cores: Annotated[int, typer.Option("--cores", help="CPUs per new worker.")] = 1,
    ram: Annotated[int, typer.Option("--ram", help="RAM GiB per new worker.")] = 4,
    gpus: Annotated[int, typer.Option("--gpus", help="GPUs per new worker.")] = 0,
    timeout: Annotated[int, typer.Option("--timeout", help="Wait timeout (seconds).")] = 1800,
    require_preflight: Annotated[
        bool,
        typer.Option(
            "--require-preflight",
            help=(
                "Enforce the network preflight gate before launching workers. "
                "Off by default (same as `cluster start`)."
            ),
        ),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Grow or shrink a fixed worker pool to this many sessions.

    `scale 0` stops workers and keeps the manager. For Ray to add/remove
    workers by itself, use `cluster start --autoscaling`.

    Examples:
      astroai cluster scale 4
      astroai cluster scale 0
    """
    result = cluster_scale_payload(
        workers,
        address=address,
        cores=cores,
        ram=ram,
        gpus=gpus,
        timeout=timeout,
        require_preflight=require_preflight,
    )
    if as_json:
        _print_json(result)
    else:
        print(f"target: {result['target']}  previous: {result['previous']}")
        print(f"phase:  {result['phase']}  joined: {result['joined_workers']}")
    raise typer.Exit(0)


# =====================================================================
# Autoscaler commands
# =====================================================================


@autoscaler_app.command("write-config")
def autoscaler_cmd_write_config(
    path: Annotated[Path, typer.Option("--path", help="Output YAML path.")],
    cluster_name: Annotated[str, typer.Option("--cluster-name", help="Ray cluster name.")],
    workers: Annotated[int, typer.Option("--workers", help="Initial min_workers.")] = 0,
    max_workers: Annotated[int, typer.Option("--max-workers", help="Autoscaler ceiling.")] = 8,
    cores: Annotated[int, typer.Option("--cores", help="CPUs per worker session.")] = 1,
    ram_gb: Annotated[int, typer.Option("--ram-gb", help="RAM GiB per worker session.")] = 4,
    gpus: Annotated[int, typer.Option("--gpus", help="GPUs per worker session.")] = 0,
    worker_image: Annotated[str | None, typer.Option("--worker-image")] = None,
    ray_version: Annotated[str | None, typer.Option("--ray-version")] = None,
    ray_head_port: Annotated[int, typer.Option("--ray-head-port")] = 6379,
    heartbeat_path: Annotated[str | None, typer.Option("--heartbeat-path")] = None,
    spill_dir: Annotated[str | None, typer.Option("--spill-dir")] = None,
    idle_timeout_minutes: Annotated[
        int | None,
        typer.Option(
            "--idle-timeout-minutes",
            help="Idle workers are terminated after this many minutes (default: env "
            "RAY_AUTOSCALING_IDLE_TIMEOUT_MINUTES or 5).",
        ),
    ] = None,
) -> None:
    """Write YAML so Ray's own autoscaler can start and stop CANFAR workers.

    Feed the file to `ray start --head --autoscaling-config=<path>` on the
    manager head. That is not `cluster start` and not `run`. Most users
    should `cluster start --autoscaling` instead.

    Example:
      astroai autoscaler write-config --path /tmp/autoscaling.yaml \\
          --cluster-name default --max-workers 8 --cores 2 --ram-gb 8
    """
    from .autoscaler import write_autoscaling_config

    out = write_autoscaling_config(
        path=path,
        cluster_name=cluster_name,
        worker_count=workers,
        max_workers=max_workers,
        cores=cores,
        ram_gb=ram_gb,
        gpus=gpus,
        worker_image=worker_image,
        ray_version=ray_version,
        ray_head_port=ray_head_port,
        heartbeat_path=heartbeat_path,
        spill_dir=spill_dir,
        idle_timeout_minutes=idle_timeout_minutes,
    )
    print(out)


# =====================================================================
# Dashboard commands
# =====================================================================


def dashboard_url_payload(address: str | None = None) -> str:
    """Resolve the Ray Dashboard / Jobs URL — CLI + MCP shared.

    Raises RuntimeError when nothing is resolvable.
    """
    from .dashboard import resolve_dashboard_url

    url = resolve_dashboard_url(address)
    if not url:
        raise RuntimeError(
            "No dashboard URL resolvable. Start a ray-manager session and run "
            "`astroai cluster start` first."
        )
    return url


@dashboard_app.command("url")
def dashboard_cmd_url(
    address: Annotated[str | None, typer.Option("--address")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print the Ray Dashboard URL for the current cluster."""
    try:
        url = dashboard_url_payload(address)
    except RuntimeError as exc:
        _cli_fail(exc)
    if as_json:
        _print_json({"dashboard_url": url})
    else:
        print(url)


@dashboard_app.command("proxy")
def dashboard_cmd_proxy(
    port: Annotated[int, typer.Option("--port", help="Local port to bind.")] = 9000,
    address: Annotated[str | None, typer.Option("--address")] = None,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
) -> None:
    """Local proxy so a notebook or marimo cell can embed the Ray Dashboard.

    Example:
      astroai cluster dashboard proxy --port 9000
      then <iframe src="http://127.0.0.1:9000/">
    """
    from .dashboard import DashboardProxy, resolve_dashboard_url

    url = resolve_dashboard_url(address)
    if not url:
        raise typer.BadParameter("No dashboard URL resolvable (see `astroai cluster dashboard`).")
    if url.endswith("/dashboard"):
        url = url[: -len("/dashboard")] + "/"
    elif not url.endswith("/"):
        url += "/"

    proxy = DashboardProxy(url, host=host, port=port)
    proxy.start()
    print(f"Ray Dashboard proxy: {proxy.url}")
    print(f"upstream:            {url}")
    print("Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        proxy.stop()


@mcp_app.command("serve")
def mcp_cmd_serve() -> None:
    """Serve cluster and job tools over stdio for agents.

    Tools: cluster start/check/scale, dashboard URL, and job
    run/submit/list/status/logs/cancel. Same functions as the CLI.

        astroai mcp serve
    """
    from .mcp import serve_stdio

    raise typer.Exit(serve_stdio())


@dashboard_app.command("iframe")
def dashboard_cmd_iframe(
    address: Annotated[str | None, typer.Option("--address")] = None,
    height: Annotated[int, typer.Option("--height")] = 900,
) -> None:
    """Print an HTML iframe that embeds the Ray Dashboard (for a notebook cell)."""
    from .dashboard import dashboard_iframe_html, resolve_dashboard_url

    url = resolve_dashboard_url(address)
    if not url:
        raise typer.BadParameter("No dashboard URL resolvable (see `astroai cluster dashboard`).")
    print(dashboard_iframe_html(url, height=height))


@dashboard_app.callback(invoke_without_command=True)
def dashboard_default(ctx: typer.Context) -> None:
    """Print the Ray Dashboard URL when no subcommand is given."""
    parent = ctx.parent.info_name if ctx.parent else ""
    if parent != "cluster":
        print(
            "warning: `astroai dashboard` is now `astroai cluster dashboard`",
            file=sys.stderr,
        )
    if ctx.invoked_subcommand is not None:
        return
    dashboard_cmd_url(address=None, as_json=False)


def register(parent: typer.Typer, *, jobs_as: str = "jobs") -> None:
    """Mount cluster/job commands on the ``astroai`` CLI.

    Job verbs that would collide with session ``status`` go under ``jobs_as``.
    ``run`` stays a top-level command.
    """
    parent.add_typer(cluster_app, name="cluster")
    parent.add_typer(dashboard_app, name="dashboard", hidden=True)
    parent.add_typer(autoscaler_app, name="autoscaler", hidden=True)
    parent.add_typer(mcp_app, name="mcp", hidden=True)
    parent.command(
        "run",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(cmd_run)
    jobs = typer.Typer(
        name=jobs_as,
        help="List, watch, and stop Ray jobs.",
        no_args_is_help=True,
        add_completion=False,
    )
    jobs.command("submit")(cmd_submit)
    jobs.command("status")(cmd_status)
    jobs.command("logs")(cmd_logs)
    jobs.command("wait")(cmd_wait)
    jobs.command("cancel")(cmd_cancel)
    jobs.command("list")(cmd_list)
    parent.add_typer(jobs, name=jobs_as)


if __name__ == "__main__":
    app()
