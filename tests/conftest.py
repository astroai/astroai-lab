from __future__ import annotations

import os

import pytest

from astroai_lab.config.settings import get_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear any host environment variables that might pollute tests
    keys_to_remove = []
    for key in os.environ:
        if key.startswith("ASTROAI_LAB_") or key in (
            "UV_CACHE_DIR",
            "PIP_CACHE_DIR",
            "PIXI_CACHE_DIR",
            "RATTLER_CACHE_DIR",
            "MAMBA_PKGS_DIRS",
            "WORK",
            "SCRATCH",
            "PROJECT",
            "XDG_CACHE_HOME",
        ):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        monkeypatch.delenv(key, raising=False)

    # Version probes can hang on some installed CLIs; keep unit tests offline.
    monkeypatch.setenv("ASTROAI_LAB_PROBE_VERSION", "0")

    # get_settings() caches a pydantic model that snapshots env vars at first
    # call; clear it so a previous test's monkeypatched WORK/SCRATCH cannot
    # leak into later tests through the cached object.
    get_settings.cache_clear()
