from __future__ import annotations

import os
from pathlib import Path


def scratch_cache_root(work: Path, scratch: Path | None) -> Path:
    user = os.environ.get("USER") or "user"
    if scratch is not None:
        return scratch / f".cache-{user}"
    return work / f".cache-{user}"


def find_arc_project_root(start: Path | None = None) -> Path | None:
    path = (start or Path.cwd()).resolve()
    if not Path("/arc/projects").is_dir():
        return None
    while path != path.parent:
        if path.parent == Path("/arc/projects"):
            return path
        path = path.parent
    return None
