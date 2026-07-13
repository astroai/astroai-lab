from __future__ import annotations

from pathlib import Path

import pytest

from astroai_lab import config_dir, saves_dir
from astroai_lab.config.settings import LabSettings, get_settings
from astroai_lab.core.paths import resolve_paths


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def lab_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ASTROAI_LAB_WORK_DIR", raising=False)
    monkeypatch.delenv("ASTROAI_LAB_SCRATCH_DIR", raising=False)
    monkeypatch.delenv("ASTROAI_LAB_SAVE_DIR", raising=False)
    monkeypatch.delenv("TMP_SRC_DIR", raising=False)
    return home


def test_config_dirs_under_astroai(lab_home: Path) -> None:
    assert config_dir() == lab_home / ".astroai" / "lab"
    assert saves_dir() == lab_home / ".astroai" / "lab" / "saves"


def test_work_dir_from_astroai_lab_env(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = lab_home / "work"
    work.mkdir()
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    settings = LabSettings()
    assert settings.resolve_work_dir() == work


def test_work_dir_falls_back_to_tmp_src(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srcdir = lab_home / "srcdir"
    srcdir.mkdir()
    monkeypatch.setenv("TMP_SRC_DIR", str(srcdir))
    settings = LabSettings()
    assert settings.resolve_work_dir() == srcdir


def test_save_dir_default(lab_home: Path) -> None:
    settings = LabSettings()
    assert settings.resolve_save_dir() == saves_dir()


def test_save_dir_override(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = lab_home / "custom-saves"
    monkeypatch.setenv("ASTROAI_LAB_SAVE_DIR", str(custom))
    settings = LabSettings()
    assert settings.resolve_save_dir() == custom


def test_resolve_paths(lab_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = lab_home / "srcdir"
    work.mkdir()
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    paths = resolve_paths()
    assert paths.work_dir == work
    assert paths.config_dir == lab_home / ".astroai" / "lab"


def test_migrates_legacy_canfar_lab_config(lab_home: Path) -> None:
    from astroai_lab import _migrated_homes, config_dir

    _migrated_homes.clear()
    legacy = lab_home / ".canfar" / "lab"
    legacy.mkdir(parents=True)
    (legacy / "config.yaml").write_text("default_pm: uv\n")
    assert config_dir() == lab_home / ".astroai" / "lab"
    assert (lab_home / ".astroai" / "lab" / "config.yaml").read_text() == "default_pm: uv\n"
