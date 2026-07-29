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
