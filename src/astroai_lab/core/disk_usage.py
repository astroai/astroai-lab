"""Home/project disk usage with CephFS directory-quota awareness.

CANFAR sets per-home quotas via ``ceph.quota.max_bytes`` on ``/arc/home/<user>``.
Plain ``statvfs`` / ``df`` often report the shared filesystem (or a stale view),
so percentages can look frozen during a session. Prefer Ceph xattrs when present;
``ceph.dir.rbytes`` is MDS-maintained and can lag briefly — that is a Ceph
limitation, not a caching bug in astroai-lab.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DiskUsage:
    path: str
    used_bytes: int
    total_bytes: int
    free_bytes: int
    pct: int
    source: str  # ceph-xattr | statvfs | unknown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _xattr_int(path: Path, name: str) -> int | None:
    try:
        raw = os.getxattr(path, name)
    except (OSError, AttributeError):
        return None
    try:
        text = raw.decode("utf-8", errors="ignore").strip() if isinstance(raw, bytes) else str(raw)
        text = "".join(ch for ch in text if ch.isdigit())
        if not text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _ceph_dir_usage(path: Path) -> DiskUsage | None:
    """Walk up from path looking for ceph.quota.max_bytes + ceph.dir.rbytes."""
    cur = path.resolve()
    for _ in range(8):
        if not cur.is_dir():
            break
        max_bytes = _xattr_int(cur, "ceph.quota.max_bytes")
        if max_bytes is not None and max_bytes > 0:
            used = _xattr_int(cur, "ceph.dir.rbytes")
            if used is None:
                # Quota set but rbytes missing — fall through to statvfs.
                break
            used = max(0, used)
            free = max(max_bytes - used, 0)
            pct = int((used / max_bytes) * 100) if max_bytes else 0
            return DiskUsage(
                path=str(cur),
                used_bytes=used,
                total_bytes=max_bytes,
                free_bytes=free,
                pct=min(pct, 100),
                source="ceph-xattr",
            )
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _statvfs_usage(path: Path) -> DiskUsage | None:
    if not path.is_dir():
        return None
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    fr = st.f_frsize
    total = st.f_blocks * fr
    if total <= 0:
        return None
    # f_bavail = space available to the calling user (matches `df` Use%).
    free = st.f_bavail * fr
    used = max(total - free, 0)
    pct = int((used / total) * 100)
    return DiskUsage(
        path=str(path),
        used_bytes=used,
        total_bytes=total,
        free_bytes=free,
        pct=min(pct, 100),
        source="statvfs",
    )


def disk_usage(path: Path) -> DiskUsage | None:
    """Best-effort usage for path: Ceph directory quota xattrs, else statvfs."""
    if not path.is_dir():
        return None
    ceph = _ceph_dir_usage(path)
    if ceph is not None:
        return ceph
    return _statvfs_usage(path)


def quota_used_pct(path: Path) -> int | None:
    """Percent used (0–100), or None if unknown."""
    info = disk_usage(path)
    return None if info is None else info.pct
