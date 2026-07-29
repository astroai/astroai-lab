"""One-click CANFAR batch compute for OpenResearch.

Ensures a ray-manager session exists, (best-effort) starts workers, and wires
OpenResearch ``orx`` to use ``--backend ray`` against that manager's Jobs URL —
without the user needing to know Ray terminology.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_MANAGER_NAME = "astroai-compute"
DEFAULT_MANAGER_CPU = 2
DEFAULT_MANAGER_RAM_GB = 8
DEFAULT_WORKERS = 2
DEFAULT_WORKER_CPU = 1
DEFAULT_WORKER_RAM_GB = 4
DEFAULT_WORKER_GPU = 0


def _config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg)
    return Path.home() / ".config"


def _orx_config_dir() -> Path:
    return _config_home() / "openresearch"


def _image_tag() -> str:
    return (
        os.environ.get("RAY_IMAGE_TAG")
        or os.environ.get("BUILD_TAG")
        or os.environ.get("ASTROAI_IMAGE_TAG")
        or "26.07"
    ).strip()


def manager_image() -> str:
    registry = os.environ.get("ASTROAI_REGISTRY", "images.canfar.net").strip()
    owner = os.environ.get("ASTROAI_OWNER", "astroai").strip()
    return f"{registry}/{owner}/ray-manager:{_image_tag()}"


def _run(cmd: list[str], *, timeout: int) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        return 1, "", str(exc)


def _parse_json_blob(text: str) -> Any | None:
    raw = (text or "").strip()
    if not raw:
        return None
    for marker in ("[", "{"):
        idx = raw.find(marker)
        if idx >= 0:
            raw = raw[idx:]
            break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def canfar_sessions(*, timeout: int = 30) -> list[dict[str, Any]]:
    if shutil.which("canfar") is None:
        return []
    rc, out, _err = _run(["canfar", "ps", "--json"], timeout=timeout)
    if rc != 0:
        return []
    data = _parse_json_blob(out)
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _session_image(row: dict[str, Any]) -> str:
    return str(row.get("image") or row.get("imageName") or "")


def _session_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "")


def _session_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "")


def _session_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("sessionId") or "")


def _session_connect_url(row: dict[str, Any]) -> str:
    url = str(row.get("connectURL") or row.get("connectUrl") or "").strip()
    if url and not url.endswith("/"):
        url += "/"
    return url


def find_manager_sessions(sessions: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = sessions if sessions is not None else canfar_sessions()
    out: list[dict[str, Any]] = []
    for row in rows:
        status = _session_status(row)
        if status not in {"Running", "Pending"}:
            continue
        image = _session_image(row).lower()
        name = _session_name(row).lower()
        if "ray-manager" in image or name in {
            DEFAULT_MANAGER_NAME,
            "raymgr",
            "orx-ray-stg",
            "ray-manager",
            "astroai-compute",
        }:
            out.append(row)
    return out


def create_manager_session(
    *,
    name: str = DEFAULT_MANAGER_NAME,
    cpu: int = DEFAULT_MANAGER_CPU,
    ram_gb: int = DEFAULT_MANAGER_RAM_GB,
    timeout: int = 120,
) -> dict[str, Any]:
    if shutil.which("canfar") is None:
        raise RuntimeError("canfar CLI not on PATH — run canfar login in webterm first")
    image = manager_image()
    cmd = [
        "canfar",
        "create",
        "--name",
        name,
        "--cpu",
        str(cpu),
        "--memory",
        str(ram_gb),
        "contributed",
        image,
    ]
    rc, out, err = _run(cmd, timeout=timeout)
    text = (out or "") + "\n" + (err or "")
    if rc != 0:
        raise RuntimeError(f"canfar create failed: {(err or out or 'unknown').strip()}")
    # Prefer fresh session list.
    time.sleep(2)
    for row in find_manager_sessions():
        if _session_name(row) == name or name in _session_name(row):
            return {
                "id": _session_id(row),
                "name": _session_name(row),
                "status": _session_status(row),
                "connectURL": _session_connect_url(row),
                "create_output": text.strip(),
            }
    m = re.search(r"ID:\s*([a-z0-9]+)", text, re.I)
    sid = m.group(1) if m else ""
    return {
        "id": sid,
        "name": name,
        "status": "Pending",
        "connectURL": "",
        "create_output": text.strip(),
    }


def wait_manager_running(
    session_id: str,
    *,
    timeout_seconds: int = 600,
    poll_seconds: float = 5.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {"id": session_id, "status": "Unknown"}
    while time.time() < deadline:
        for row in canfar_sessions():
            if _session_id(row) == session_id:
                last = {
                    "id": session_id,
                    "name": _session_name(row),
                    "status": _session_status(row),
                    "connectURL": _session_connect_url(row),
                    "image": _session_image(row),
                }
                st = last["status"]
                if st == "Running" and last["connectURL"]:
                    return last
                if st in {"Failed", "Error", "Terminating", "Succeeded", "Completed"}:
                    raise RuntimeError(f"Manager session ended with status {st}")
                break
        time.sleep(poll_seconds)
    raise RuntimeError(
        f"Timed out waiting for manager {session_id} to become Running "
        f"(last status={last.get('status')})"
    )


def _ssl_context() -> ssl.SSLContext | None:
    pem = Path.home() / ".ssl" / "cadcproxy.pem"
    if not pem.is_file():
        return None
    try:
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(str(pem))
        return ctx
    except ssl.SSLError:
        return None


def http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    ctx = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = getattr(resp, "status", 200) or 200
            try:
                return int(code), json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return int(code), {"raw": raw}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            payload: Any = json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            payload = {"error": raw or str(exc)}
        return int(exc.code), payload
    except Exception as exc:  # noqa: BLE001 — surface any transport failure
        return 0, {"error": str(exc)}


def jobs_url_from_connect(connect_url: str) -> str:
    base = connect_url.rstrip("/") + "/"
    # Dashboard reverse-proxy exposes Jobs API under /dashboard/
    return base + "dashboard"


def wait_manager_ready(connect_url: str, *, timeout_seconds: int = 180) -> dict[str, Any]:
    base = connect_url.rstrip("/")
    deadline = time.time() + timeout_seconds
    last: Any = {}
    while time.time() < deadline:
        code, payload = http_json("GET", f"{base}/readyz", timeout=15)
        last = payload
        if code == 200 and isinstance(payload, dict) and payload.get("ready"):
            return payload
        time.sleep(3)
    raise RuntimeError(f"Manager UI not ready at {base}/readyz (last={last})")


def persist_connect_url(connect_url: str, *, cluster_id: str | None = None) -> Path:
    cid = (cluster_id or os.environ.get("RAY_CLUSTER_ID") or "default").strip() or "default"
    root = Path.home() / ".astroai" / "ray" / "clusters" / cid
    root.mkdir(parents=True, exist_ok=True)
    path = root / "connect-url"
    path.write_text(connect_url.rstrip("/") + "/\n", encoding="utf-8")
    return path


def read_persisted_connect_url() -> str | None:
    clusters = Path.home() / ".astroai" / "ray" / "clusters"
    if not clusters.is_dir():
        return None
    candidates: list[tuple[float, str]] = []
    for root in clusters.iterdir():
        if not root.is_dir():
            continue
        path = root / "connect-url"
        if not path.is_file():
            continue
        try:
            url = path.read_text(encoding="utf-8").strip()
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if url:
            candidates.append((mtime, url if url.endswith("/") else url + "/"))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def wire_orx(
    *,
    jobs_address: str,
    make_default: bool = True,
) -> dict[str, Any]:
    """Write OpenResearch Ray settings + optional default compute target."""
    cfg = _orx_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    address = jobs_address.rstrip("/")
    ray_path = cfg / "ray.json"
    ray_path.write_text(
        json.dumps({"address": address}, indent=2) + "\n",
        encoding="utf-8",
    )
    settings_path = cfg / "settings.json"
    settings: dict[str, Any] = {}
    if settings_path.is_file():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings = loaded
        except (OSError, json.JSONDecodeError):
            settings = {}
    if make_default:
        settings["defaultBackend"] = "ray"
        # Optional flavor left unset — orx reserves no entrypoint CPUs by default.
        settings.pop("defaultFlavor", None)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    # Env for this process / child shells that inherit from a wrapper.
    os.environ["ASTROAI_RAY_JOBS_ADDRESS"] = address
    return {
        "ray_json": str(ray_path),
        "settings_json": str(settings_path),
        "address": address,
        "default_backend": settings.get("defaultBackend"),
    }


def manager_status(connect_url: str) -> dict[str, Any]:
    code, payload = http_json("GET", connect_url.rstrip("/") + "/api/v1/status", timeout=30)
    if isinstance(payload, dict):
        payload = {**payload, "http_status": code}
        return payload
    return {"http_status": code, "error": payload}


def ensure_workers(
    connect_url: str,
    *,
    worker_count: int = DEFAULT_WORKERS,
    cores: int = DEFAULT_WORKER_CPU,
    ram_gb: int = DEFAULT_WORKER_RAM_GB,
    gpus: int = DEFAULT_WORKER_GPU,
    skip_preflight: bool = False,
    preflight_timeout: int = 300,
    create_timeout: int = 900,
) -> dict[str, Any]:
    """Run preflight (unless skipped) and create a small worker cluster."""
    base = connect_url.rstrip("/")
    result: dict[str, Any] = {
        "preflight": None,
        "cluster": None,
        "workers_requested": worker_count,
        "require_preflight": not skip_preflight,
    }

    status = manager_status(connect_url)
    phase = str(status.get("phase") or "")
    workers = status.get("workers") or []
    joined = [
        w
        for w in workers
        if isinstance(w, dict) and (w.get("ray_joined") or w.get("phase") == "Joined")
    ]
    if phase in {"Running", "Degraded"} and joined:
        result["cluster"] = status
        result["already_ready"] = True
        result["joined_workers"] = len(joined)
        return result

    require_preflight = not skip_preflight
    if require_preflight:
        # Async start then poll status.preflight — sync can exceed hub timeouts.
        code, pf = http_json(
            "POST",
            f"{base}/api/v1/preflight/run?async=true",
            timeout=30,
        )
        result["preflight_accepted"] = {"http_status": code, "body": pf}
        deadline = time.time() + preflight_timeout
        passed = False
        last_pf: Any = None
        while time.time() < deadline:
            st = manager_status(connect_url)
            last_pf = st.get("preflight")
            if isinstance(last_pf, dict) and last_pf.get("passed"):
                passed = True
                break
            if isinstance(last_pf, dict) and last_pf.get("passed") is False and last_pf.get("done"):
                break
            # Also check active operation finished with failure via status message
            time.sleep(5)
        result["preflight"] = last_pf
        if not passed:
            # Fall back: still try create without preflight so head Jobs work;
            # workers may fail to join on isolated networks.
            require_preflight = False
            result["preflight_fallback"] = True
            result["require_preflight"] = False

    body = {
        "name": "orx",
        "worker_count": max(1, worker_count),
        "cores": cores,
        "ram_gb": ram_gb,
        "gpus": gpus,
        "min_joined": 1,
        "partial_policy": "accept_partial",
        "require_preflight": require_preflight,
    }
    code, created = http_json(
        "POST",
        f"{base}/api/v1/cluster/create?async=true",
        body=body,
        timeout=60,
    )
    result["create_accepted"] = {"http_status": code, "body": created}
    if code not in {200, 202} and code != 400:
        # Non-async fallback
        code, created = http_json(
            "POST",
            f"{base}/api/v1/cluster/create",
            body=body,
            timeout=create_timeout,
        )
        result["cluster"] = created if isinstance(created, dict) else {"raw": created}
        result["create_http_status"] = code
        return result

    # Poll until Running/Degraded/Failed or timeout
    deadline = time.time() + create_timeout
    last_st: dict[str, Any] = {}
    while time.time() < deadline:
        last_st = manager_status(connect_url)
        phase = str(last_st.get("phase") or "")
        if phase in {"Running", "Degraded", "Failed", "Stopped", "Error"}:
            break
        time.sleep(5)
    result["cluster"] = last_st
    workers = last_st.get("workers") or []
    result["joined_workers"] = len(
        [
            w
            for w in workers
            if isinstance(w, dict) and (w.get("ray_joined") or w.get("phase") == "Joined")
        ]
    )
    return result


def ensure_compute(
    *,
    workers: int = DEFAULT_WORKERS,
    worker_gpus: int = DEFAULT_WORKER_GPU,
    skip_preflight: bool = False,
    create_manager: bool = True,
    wire: bool = True,
    manager_name: str = DEFAULT_MANAGER_NAME,
) -> dict[str, Any]:
    """End-to-end: manager session → workers (best effort) → wire orx."""
    out: dict[str, Any] = {
        "ok": False,
        "steps": [],
        "manager": None,
        "jobs_address": None,
        "orx": None,
        "workers": None,
        "user_message": "",
    }

    sessions = canfar_sessions()
    managers = find_manager_sessions(sessions)
    running = [m for m in managers if _session_status(m) == "Running" and _session_connect_url(m)]
    pending = [m for m in managers if _session_status(m) == "Pending"]

    manager: dict[str, Any] | None = None
    if running:
        row = running[0]
        manager = {
            "id": _session_id(row),
            "name": _session_name(row),
            "status": "Running",
            "connectURL": _session_connect_url(row),
            "reused": True,
        }
        out["steps"].append("reuse_manager")
    elif pending and create_manager:
        row = pending[0]
        out["steps"].append("wait_pending_manager")
        manager = wait_manager_running(_session_id(row))
        manager["reused"] = True
    elif create_manager:
        out["steps"].append("create_manager")
        created = create_manager_session(name=manager_name)
        sid = created.get("id") or ""
        if not sid:
            raise RuntimeError("canfar create did not return a session id")
        manager = wait_manager_running(sid)
        manager["reused"] = False
    else:
        # Discover from persisted connect-url only
        url = read_persisted_connect_url()
        if not url:
            out["user_message"] = (
                "No batch-compute session found. Click Start batch compute "
                "(needs canfar login on this home)."
            )
            return out
        manager = {"id": "", "name": "", "status": "Unknown", "connectURL": url, "reused": True}
        out["steps"].append("persisted_connect_url")

    assert manager is not None
    connect = str(manager.get("connectURL") or "").strip()
    if not connect:
        raise RuntimeError("Manager has no connect URL yet")
    if not connect.endswith("/"):
        connect += "/"
    manager["connectURL"] = connect
    out["manager"] = manager

    out["steps"].append("wait_readyz")
    wait_manager_ready(connect)
    persist_connect_url(connect)

    jobs = jobs_url_from_connect(connect)
    out["jobs_address"] = jobs

    if workers > 0:
        out["steps"].append("ensure_workers")
        try:
            out["workers"] = ensure_workers(
                connect,
                worker_count=workers,
                gpus=worker_gpus,
                skip_preflight=skip_preflight,
            )
        except Exception as exc:  # noqa: BLE001
            out["workers"] = {"error": str(exc)}
            out["steps"].append("workers_failed_continuing")

    if wire:
        out["steps"].append("wire_orx")
        out["orx"] = wire_orx(jobs_address=jobs, make_default=True)

    joined = 0
    if isinstance(out.get("workers"), dict):
        joined = int(out["workers"].get("joined_workers") or 0)
    out["ok"] = True
    if joined > 0:
        out["user_message"] = (
            f"Batch compute is ready ({joined} worker(s)). "
            "OpenResearch will use it automatically — set your agent API keys and run experiments."
        )
    else:
        out["user_message"] = (
            "Batch compute manager is ready (Jobs API wired). "
            "Workers may still be joining or network preflight may have failed — "
            "small jobs still work; check AstroAI → Batch compute if runs stay Pending."
        )
    return out
