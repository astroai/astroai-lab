from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from astroai_lab import config_dir, saves_dir


class PushSettings(BaseModel):
    auto_save: bool = True
    require_clean_git: bool = False


class LabSettings(BaseSettings):
    """Session workbench settings (ASTROAI_LAB_* env vars + optional config.yaml)."""

    model_config = SettingsConfigDict(
        env_prefix="ASTROAI_LAB_",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    work_dir: Path | None = Field(default=None)
    scratch_dir: Path | None = Field(default=None)
    save_dir: Path | None = Field(default=None)
    default_pm: Literal["pixi", "uv"] = "pixi"
    clone_from_env: str | None = None
    push: PushSettings = Field(default_factory=PushSettings)

    def resolve_work_dir(self) -> Path:
        for raw in (
            self.work_dir,
            _env_path("ASTROAI_LAB_WORK_DIR"),
            _env_path("TMP_SRC_DIR"),
            _env_path("ASTROAI_LAB_DEFAULT_SRC_DIR"),
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
            _env_path("ASTROAI_LAB_SCRATCH_DIR"),
            _env_path("TMP_SCRATCH_DIR"),
            _env_path("ASTROAI_LAB_DEFAULT_SCRATCH_DIR"),
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
        custom = _env_path("ASTROAI_LAB_SAVE_DIR")
        if custom is not None:
            return custom
        return saves_dir()


def config_file_path() -> Path:
    return config_dir() / "config.yaml"


def _env_path(name: str) -> Path | None:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else None


def _yaml_settings_source() -> dict:
    path = config_file_path()
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


@lru_cache
def get_settings() -> LabSettings:
    yaml_data = _yaml_settings_source()
    return LabSettings(**yaml_data)
