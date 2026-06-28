from __future__ import annotations

import os
import pwd
from pathlib import Path


def user_tag() -> str:
    """Match shell ``${USER:-$(id -un)}`` for cache/runtime directory names."""
    for key in ("USER", "LOGNAME"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        return str(os.getuid())


def scratch_cache_root(work: Path, scratch: Path | None) -> Path:
    user = user_tag()
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
