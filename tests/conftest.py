from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear any host environment variables that might pollute tests
    keys_to_remove = []
    for key in os.environ:
        if key.startswith("ASTROAI_LAB_") and key not in (
            "ASTROAI_LAB_WORK_DIR",
            "ASTROAI_LAB_SCRATCH_DIR",
            "ASTROAI_LAB_DEFAULT_SCRATCH_DIR",
            "ASTROAI_LAB_DEFAULT_SRC_DIR",
        ):
            keys_to_remove.append(key)
        elif key in ("UV_CACHE_DIR", "PIP_CACHE_DIR", "PIXI_CACHE_DIR", "MAMBA_PKGS_DIRS"):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        monkeypatch.delenv(key, raising=False)
