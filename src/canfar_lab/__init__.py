"""canfar-lab — in-session workbench for the CANFAR Science Platform."""

from pathlib import Path

__version__ = "0.1.0"


def config_dir() -> Path:
    """Workbench config directory (~/.canfar/lab)."""
    return Path.home() / ".canfar" / "lab"


def saves_dir() -> Path:
    """Default directory for saved lockfile environments."""
    return config_dir() / "saves"


__all__ = ["__version__", "config_dir", "saves_dir"]
