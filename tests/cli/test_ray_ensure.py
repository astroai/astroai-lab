"""Tests for one-click batch compute helpers."""

from __future__ import annotations

import json
from pathlib import Path

from astroai_lab.cli.ray_ensure import (
    find_manager_sessions,
    jobs_url_from_connect,
    wire_orx,
)


def test_jobs_url_from_connect() -> None:
    assert (
        jobs_url_from_connect("https://workloads.example/session/contrib/abc")
        == "https://workloads.example/session/contrib/abc/dashboard"
    )
    assert jobs_url_from_connect("https://x/").endswith("/dashboard")


def test_find_manager_sessions_filters() -> None:
    rows = [
        {
            "id": "a",
            "name": "astroai-compute",
            "status": "Running",
            "image": "images.canfar.net/astroai/ray-manager:26.07",
            "connectURL": "https://x/session/contrib/a/",
        },
        {
            "id": "b",
            "name": "webterm",
            "status": "Running",
            "image": "images.canfar.net/astroai/webterm:26.07",
            "connectURL": "https://x/session/contrib/b/",
        },
        {
            "id": "c",
            "name": "raymgr",
            "status": "Pending",
            "image": "images.canfar.net/astroai/ray-manager:26.07",
        },
        {
            "id": "d",
            "name": "old",
            "status": "Succeeded",
            "image": "images.canfar.net/astroai/ray-manager:26.07",
        },
    ]
    found = find_manager_sessions(rows)
    ids = {r["id"] for r in found}
    assert ids == {"a", "c"}


def test_wire_orx(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    out = wire_orx(jobs_address="https://example/dashboard/", make_default=True)
    assert out["address"] == "https://example/dashboard"
    ray = json.loads(Path(out["ray_json"]).read_text(encoding="utf-8"))
    settings = json.loads(Path(out["settings_json"]).read_text(encoding="utf-8"))
    assert ray["address"] == "https://example/dashboard"
    assert settings["defaultBackend"] == "ray"


def test_read_orx_compute_config(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli.ray_ensure import read_orx_compute_config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("ASTROAI_RAY_JOBS_ADDRESS", raising=False)
    monkeypatch.delenv("RAY_DASHBOARD_URL", raising=False)
    empty = read_orx_compute_config()
    assert empty["wired"] is False
    assert empty["address"] is None

    wire_orx(jobs_address="https://jobs.example/dashboard", make_default=True)
    wired = read_orx_compute_config()
    assert wired["wired"] is True
    assert wired["address"] == "https://jobs.example/dashboard"
    assert wired["default_backend"] == "ray"
    assert wired["address_source"] == "ray.json"


def test_collect_ray_status_separates_wired_from_discoverable(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    from astroai_lab.cli import ray_cmd as rc

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("ASTROAI_RAY_JOBS_ADDRESS", raising=False)
    (tmp_path / "home").mkdir()
    monkeypatch.setattr(
        rc,
        "canfar_sessions",
        lambda: [
            {
                "id": "m1",
                "name": "astroai-compute",
                "status": "Running",
                "connectURL": "https://ws.example/session/contrib/m1/",
                "image": "images.canfar.net/astroai/ray-manager:26.07",
            }
        ],
    )
    monkeypatch.setattr(rc, "read_persisted_connect_url", lambda: None)
    payload = rc.collect_ray_status()
    assert payload["manager_running"] is True
    assert payload["jobs_address_discoverable"]
    assert payload["ray_address"] is None
    assert payload["compute_ready"] is False
    assert payload["orx_wired"] is False
    assert payload["connect_url"]

    # Stale heartbeat / persisted URL alone must not look like a live manager.
    monkeypatch.setattr(rc, "canfar_sessions", lambda: [])
    monkeypatch.setattr(
        rc,
        "read_persisted_connect_url",
        lambda: "https://ws.example/session/contrib/old/",
    )
    (tmp_path / "home" / ".astroai" / "ray" / "clusters" / "default").mkdir(parents=True)
    hb = tmp_path / "home" / ".astroai" / "ray" / "clusters" / "default" / "manager-heartbeat"
    hb.write_text("stale\n", encoding="utf-8")
    stale = rc.collect_ray_status()
    assert stale["manager_running"] is False
    assert stale["connect_url"] is None
    assert stale["compute_ready"] is False
    assert "Stale" in (stale.get("hint") or "") or "stale" in (stale.get("hint") or "").lower()

    monkeypatch.setattr(
        rc,
        "canfar_sessions",
        lambda: [
            {
                "id": "m1",
                "name": "astroai-compute",
                "status": "Running",
                "connectURL": "https://ws.example/session/contrib/m1/",
                "image": "images.canfar.net/astroai/ray-manager:26.07",
            }
        ],
    )
    wire_orx(jobs_address="https://ws.example/session/contrib/m1/dashboard", make_default=True)
    payload2 = rc.collect_ray_status()
    assert payload2["compute_ready"] is True
    assert payload2["orx_wired"] is True
    assert payload2["ray_address"] == "https://ws.example/session/contrib/m1/dashboard"

def test_manager_status_normalizes_nested_phase(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    def fake_http(method, url, body=None, timeout=120.0):
        return 200, {
            "cluster": {"phase": "Running", "name": "orx"},
            "workers": [{"session_id": "w1", "ray_joined": True, "phase": "Joined"}],
            "joined_workers": 1,
            "preflight": {"passed": True, "manager_ip": "10.0.0.1"},
        }

    monkeypatch.setattr(re, "http_json", fake_http)
    st = re.manager_status("https://example/session/contrib/x/")
    assert st["phase"] == "Running"
    assert st["joined_workers"] == 1


def test_ensure_compute_soft_fails_without_canfar(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setattr(re.shutil, "which", lambda _name: None)
    monkeypatch.setattr(re, "canfar_sessions", lambda timeout=30: [])
    monkeypatch.setattr(re, "read_persisted_connect_url", lambda: None)
    out = re.ensure_compute(create_manager=True)
    assert out["ok"] is False
    assert out.get("error") == "canfar_not_found"
    assert "canfar" in out["user_message"].lower()


def test_ensure_workers_polls_on_create_409(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    seq = [
        {
            "phase": "Idle",
            "workers": [],
            "joined_workers": 0,
            "preflight": {"passed": True},
            "operation": {"kind": "cluster_create", "running": True},
        },
        {
            "phase": "Creating",
            "workers": [{"session_id": "w1", "phase": "CANFAR Pending"}],
            "joined_workers": 0,
            "operation": {"kind": "cluster_create", "running": True},
        },
        {
            "phase": "Running",
            "workers": [{"session_id": "w1", "phase": "Ray Healthy", "ray_joined": True}],
            "joined_workers": 1,
            "operation": None,
        },
    ]
    i = {"n": 0}

    def fake_status(_url: str):
        n = min(i["n"], len(seq) - 1)
        i["n"] += 1
        return {**seq[n], "http_status": 200}

    def fake_http(method, url, body=None, timeout=120.0):
        if "preflight" in url:
            return 202, {"accepted": True}
        if "cluster/create" in url:
            return 409, {"detail": "Operation in progress: cluster_create"}
        return 200, {}

    monkeypatch.setattr(re, "manager_status", fake_status)
    monkeypatch.setattr(re, "http_json", fake_http)
    monkeypatch.setattr(re.time, "sleep", lambda _s: None)
    out = re.ensure_workers(
        "https://example/", skip_preflight=True, create_timeout=60
    )
    assert out.get("create_accepted", {}).get("http_status") == 409
    assert out.get("joined_workers") == 1
    assert "create_http_status" not in out  # did not fall into sync create


def test_ensure_workers_short_circuits_failed_preflight(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    seq = [
        {
            "phase": "Idle",
            "workers": [],
            "joined_workers": 0,
            "preflight": None,
            "operation": {"kind": "preflight", "running": True},
        },
        {
            "phase": "Idle",
            "workers": [],
            "joined_workers": 0,
            "preflight": {"passed": False, "message": "blocked", "manager_ip": "10.0.0.1"},
            "operation": {"kind": "preflight", "running": False},
        },
        {
            "phase": "Creating",
            "workers": [{"session_id": "w1", "phase": "Pending"}],
            "joined_workers": 0,
            "preflight": {"passed": False, "message": "blocked", "manager_ip": "10.0.0.1"},
        },
        {
            "phase": "Running",
            "workers": [{"session_id": "w1", "phase": "Joined", "ray_joined": True}],
            "joined_workers": 1,
            "preflight": {"passed": False, "message": "blocked", "manager_ip": "10.0.0.1"},
        },
    ]
    i = {"n": 0}

    def fake_status(_url: str):
        n = min(i["n"], len(seq) - 1)
        i["n"] += 1
        return {**seq[n], "http_status": 200}

    def fake_http(method, url, body=None, timeout=120.0):
        if "preflight" in url:
            return 202, {"accepted": True}
        if "cluster/create" in url:
            return 202, {"accepted": True}
        return 200, {}

    monkeypatch.setattr(re, "manager_status", fake_status)
    monkeypatch.setattr(re, "http_json", fake_http)
    monkeypatch.setattr(re.time, "sleep", lambda _s: None)
    out = re.ensure_workers("https://example/", preflight_timeout=60, create_timeout=60)
    assert out.get("preflight_fallback") is True
    assert out.get("joined_workers") == 1


def test_active_canfar_server_env_and_auth_show(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setenv("CANFAR_ACTIVE_SERVER", "staging")
    assert re.active_canfar_server() == "staging"
    monkeypatch.delenv("CANFAR_ACTIVE_SERVER")
    monkeypatch.setenv("ACTIVE_SERVER", "canfar")
    assert re.active_canfar_server() == "canfar"
    monkeypatch.delenv("ACTIVE_SERVER")
    monkeypatch.setattr(re.shutil, "which", lambda _n: "/usr/bin/canfar")
    monkeypatch.setattr(
        re,
        "_run",
        lambda *_a, **_k: (0, "Server   staging\n", ""),
    )
    assert re.active_canfar_server() == "staging"


def test_manager_image_and_parse_helpers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setenv("ASTROAI_REGISTRY", "images.example")
    monkeypatch.setenv("ASTROAI_OWNER", "org")
    monkeypatch.setenv("RAY_IMAGE_TAG", "26.07")
    assert re.manager_image() == "images.example/org/ray-manager:26.07"
    assert re._parse_json_blob("") is None
    assert re._parse_json_blob("noise {\"a\": 1}") == {"a": 1}
    assert re._parse_json_blob("[1, 2]") == [1, 2]


def test_canfar_sessions_and_create_manager(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setattr(re.shutil, "which", lambda _n: "/usr/bin/canfar")
    monkeypatch.setattr(
        re,
        "_run",
        lambda cmd, *, timeout: (
            0,
            json.dumps(
                [
                    {
                        "id": "m1",
                        "name": "astroai-compute",
                        "status": "Running",
                        "connectURL": "https://x/session/contrib/m1",
                        "image": "images.canfar.net/astroai/ray-manager:26.07",
                    }
                ]
            ),
            "",
        )
        if "ps" in cmd
        else (0, "Created session ID: m1\n", ""),
    )
    monkeypatch.setattr(re.time, "sleep", lambda _s: None)
    rows = re.canfar_sessions()
    assert len(rows) == 1
    created = re.create_manager_session(name="astroai-compute")
    assert created["id"] == "m1"
    assert created["connectURL"].endswith("/")


def test_wait_manager_running_and_ready(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    seq = [
        [
            {
                "id": "m1",
                "name": "astroai-compute",
                "status": "Pending",
                "connectURL": "",
                "image": "x/ray-manager:t",
            }
        ],
        [
            {
                "id": "m1",
                "name": "astroai-compute",
                "status": "Running",
                "connectURL": "https://x/session/contrib/m1/",
                "image": "x/ray-manager:t",
            }
        ],
    ]
    i = {"n": 0}

    def fake_sessions(timeout=30):
        n = min(i["n"], len(seq) - 1)
        i["n"] += 1
        return seq[n]

    monkeypatch.setattr(re, "canfar_sessions", fake_sessions)
    monkeypatch.setattr(re.time, "sleep", lambda _s: None)
    out = re.wait_manager_running("m1", timeout_seconds=30, poll_seconds=0)
    assert out["status"] == "Running"
    assert out["connectURL"].endswith("/")

    ready_i = {"n": 0}

    def fake_http(method, url, body=None, timeout=120.0):
        ready_i["n"] += 1
        if ready_i["n"] == 1:
            return 503, {"ready": False}
        return 200, {"ready": True}

    monkeypatch.setattr(re, "http_json", fake_http)
    assert re.wait_manager_ready("https://x/", timeout_seconds=30)["ready"] is True


def test_persist_and_read_connect_url(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setenv("HOME", str(tmp_path))
    path = re.persist_connect_url("https://x/session/contrib/a", cluster_id="c1")
    assert path.is_file()
    assert re.read_persisted_connect_url() == "https://x/session/contrib/a/"


def test_ensure_compute_reuses_running_manager(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(re.shutil, "which", lambda _n: "/usr/bin/canfar")
    monkeypatch.setattr(
        re,
        "canfar_sessions",
        lambda timeout=30: [
            {
                "id": "m1",
                "name": "astroai-compute",
                "status": "Running",
                "connectURL": "https://ws.example/session/contrib/m1/",
                "image": "images.canfar.net/astroai/ray-manager:26.07",
            }
        ],
    )
    monkeypatch.setattr(re, "wait_manager_ready", lambda *_a, **_k: {"ready": True})
    monkeypatch.setattr(
        re,
        "ensure_workers",
        lambda *_a, **_k: {"already_ready": True, "joined_workers": 2},
    )
    monkeypatch.setattr(re.time, "sleep", lambda _s: None)
    out = re.ensure_compute(workers=1)
    assert out["ok"] is True
    assert out["steps"][0] == "reuse_manager"
    assert out["orx"]["default_backend"] == "ray"
    assert "2 worker" in out["user_message"]


def test_ensure_compute_persisted_only(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(re, "canfar_sessions", lambda timeout=30: [])
    monkeypatch.setattr(
        re, "read_persisted_connect_url", lambda: "https://ws.example/session/contrib/old/"
    )
    monkeypatch.setattr(re, "wait_manager_ready", lambda *_a, **_k: {"ready": True})
    monkeypatch.setattr(re, "ensure_workers", lambda *_a, **_k: {"joined_workers": 0})
    out = re.ensure_compute(create_manager=False, workers=0)
    assert out["ok"] is True
    assert "persisted_connect_url" in out["steps"]
    assert out["orx"]["address"].endswith("/dashboard")


def test_ensure_workers_already_ready(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re

    monkeypatch.setattr(
        re,
        "manager_status",
        lambda _u: {
            "phase": "Running",
            "joined_workers": 3,
            "workers": [{"ray_joined": True, "phase": "Ray Healthy"}],
            "http_status": 200,
        },
    )
    out = re.ensure_workers("https://example/")
    assert out["already_ready"] is True
    assert out["joined_workers"] == 3


def test_http_json_handles_http_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astroai_lab.cli import ray_ensure as re
    import urllib.error

    class FakeFP:
        def read(self):
            return b'{"error":"nope"}'

        def close(self) -> None:
            return None

    def boom(*_a, **_k):
        raise urllib.error.HTTPError("http://x", 400, "bad", hdrs=None, fp=FakeFP())  # type: ignore[arg-type]

    monkeypatch.setattr(re.urllib.request, "urlopen", boom)
    monkeypatch.setattr(re, "_ssl_context", lambda: None)
    code, body = re.http_json("GET", "http://x")
    assert code == 400
    assert body["error"] == "nope"
