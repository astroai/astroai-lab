from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache
def bundle_root() -> Path:
    env = os.environ.get("ASTROAI_LAB_AGENT_BUNDLE", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    pkg = Path(__file__).resolve().parent.parent / "data" / "agent"
    if pkg.is_dir():
        return pkg
    raise FileNotFoundError(f"Agent bundle not found: {pkg}")
