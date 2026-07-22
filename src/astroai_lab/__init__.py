"""astroai-lab — in-session workbench for AstroAI sessions on CANFAR."""

from __future__ import annotations

import shutil
from pathlib import Path

__version__ = "0.2.0"

_migrated_homes: set[str] = set()


def _legacy_config_dir(home: Path | None = None) -> Path:
    # Legacy path before the astroai-lab rename (do not "fix" to .astroai).
    return (home or Path.home()) / ".canfar" / "lab"


def _config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".astroai" / "lab"


def _migrate_legacy_config(home: Path | None = None) -> None:
    """One-shot copy ~/.canfar/lab → ~/.astroai/lab; then ignore legacy."""
    home = home or Path.home()
    key = str(home)
    if key in _migrated_homes:
        return
    _migrated_homes.add(key)
    legacy = _legacy_config_dir(home)
    dest = _config_dir(home)
    if dest.exists() or not legacy.exists():
        return
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy, dest, dirs_exist_ok=True)
    except OSError:
        pass


def config_dir() -> Path:
    """Workbench config directory (~/.astroai/lab)."""
    _migrate_legacy_config()
    return _config_dir()


def saves_dir() -> Path:
    """Default directory for saved lockfile environments."""
    return config_dir() / "saves"


__all__ = ["__version__", "config_dir", "saves_dir"]
