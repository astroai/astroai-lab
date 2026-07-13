"""Shell integration for AstroAI lab sessions."""

from __future__ import annotations

from pathlib import Path


def data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def shell_dir() -> Path:
    return data_dir() / "shell"


def profile_sh_path() -> Path:
    return shell_dir() / "profile.sh"


def hooks_sh_path() -> Path:
    return shell_dir() / "hooks.sh"
