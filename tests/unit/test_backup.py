from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from astroai_lab.core import backup as backup_mod
from astroai_lab.errors import LabError


def test_session_id_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("skaha_sessionid", raising=False)
    assert backup_mod.session_id() == "local"


def test_session_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("skaha_sessionid", "abc123")
    assert backup_mod.session_id() == "abc123"


def test_backup_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTROAI_LAB_BACKUP_INTERVAL", raising=False)
    assert backup_mod.backup_interval_sec() == 3600


def test_backup_interval_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTROAI_LAB_BACKUP_INTERVAL", "nope")
    with pytest.raises(LabError, match="Invalid"):
        backup_mod.backup_interval_sec()


def test_backup_interval_too_small(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTROAI_LAB_BACKUP_INTERVAL", "10")
    with pytest.raises(LabError, match="too small"):
        backup_mod.backup_interval_sec()


def test_run_backup_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    work = tmp_path / "srcdir"
    work.mkdir()
    (work / "a.py").write_text("print(1)\n")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    monkeypatch.delenv("skaha_sessionid", raising=False)
    get_settings.cache_clear()

    status = backup_mod.run_backup(dry_run=True, config=home / ".astroai" / "lab")
    assert status.ok
    assert status.message == "dry-run"


def test_run_backup_rsync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    work = tmp_path / "srcdir"
    work.mkdir()
    (work / "a.py").write_text("print(1)\n")
    (work / ".venv").mkdir()
    (work / ".venv" / "x").write_text("skip")
    home = tmp_path / "home"
    home.mkdir()
    cfg = home / ".astroai" / "lab"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    monkeypatch.setenv("skaha_sessionid", "sess1")
    get_settings.cache_clear()

    with patch("astroai_lab.core.backup.quota_used_pct", return_value=10):
        status = backup_mod.run_backup(config=cfg)

    assert status.ok
    dest = home / ".astroai" / "lab" / "backups" / "sess1"
    assert (dest / "a.py").read_text() == "print(1)\n"
    assert not (dest / ".venv").exists()
    loaded = backup_mod.load_status(cfg)
    assert loaded is not None and loaded.ok


def test_run_backup_skips_high_quota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    work = tmp_path / "srcdir"
    work.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = home / ".astroai" / "lab"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    get_settings.cache_clear()

    with patch("astroai_lab.core.backup.quota_used_pct", return_value=95):
        status = backup_mod.run_backup(config=cfg)

    assert status.skipped
    assert not status.ok


def test_restore_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    home = tmp_path / "home"
    work = tmp_path / "srcdir"
    backup = home / ".astroai" / "lab" / "backups" / "local"
    backup.mkdir(parents=True)
    (backup / "restored.txt").write_text("hi\n")
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    monkeypatch.delenv("skaha_sessionid", raising=False)
    get_settings.cache_clear()

    dest = backup_mod.restore_backup(yes=True)
    assert dest == work.resolve()
    assert (work / "restored.txt").read_text() == "hi\n"
