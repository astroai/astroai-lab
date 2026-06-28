from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from canfar_lab import saves_dir


class LabSettings(BaseSettings):
    """Session workbench settings (CANFAR_LAB_* env vars)."""

    model_config = SettingsConfigDict(
        env_prefix="CANFAR_LAB_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    work_dir: Path | None = Field(
        default=None,
        description="Ephemeral code directory (git repos, pixi/uv projects).",
    )
    scratch_dir: Path | None = Field(
        default=None,
        description="Ephemeral scratch for datasets and download caches.",
    )
    save_dir: Path | None = Field(
        default=None,
        description="Persistent directory for saved lockfile environments.",
    )

    def resolve_work_dir(self) -> Path:
        for raw in (
            self.work_dir,
            _env_path("CANFAR_LAB_WORK_DIR"),
            _env_path("TMP_SRC_DIR"),
        ):
            if raw is not None and raw.is_dir() and os.access(raw, os.W_OK):
                return raw
        for candidate in (Path("/srcdir"), Path.home() / "work"):
            if candidate.is_dir() and os.access(candidate, os.W_OK):
                return candidate
        return Path.cwd()

    def resolve_scratch_dir(self) -> Path | None:
        for raw in (
            self.scratch_dir,
            _env_path("CANFAR_LAB_SCRATCH_DIR"),
            _env_path("TMP_SCRATCH_DIR"),
        ):
            if raw is not None and raw.is_dir() and os.access(raw, os.W_OK):
                return raw
        default = Path("/scratch")
        if default.is_dir() and os.access(default, os.W_OK):
            return default
        return None

    def resolve_save_dir(self) -> Path:
        if self.save_dir is not None:
            return self.save_dir
        custom = _env_path("CANFAR_LAB_SAVE_DIR")
        if custom is not None:
            return custom
        return saves_dir()


def _env_path(name: str) -> Path | None:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else None


@lru_cache
def get_settings() -> LabSettings:
    return LabSettings()
