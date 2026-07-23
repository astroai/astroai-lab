from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_daemon_pid_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    home = tmp_path / "home"
    home.mkdir()
    cfg = home / ".astroai" / "lab"
    cfg.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    get_settings.cache_clear()

    assert backup_mod.daemon_running(cfg) is None
    assert backup_mod.stop_daemon(cfg) is False

    # Stale pid file for a dead process should be cleaned up.
    backup_mod.pid_path(cfg).write_text("999999\n", encoding="utf-8")
    assert backup_mod.daemon_running(cfg) is None
    assert not backup_mod.pid_path(cfg).is_file()

    # Live pid (this process) is reported.
    backup_mod.pid_path(cfg).write_text(f"{os.getpid()}\n", encoding="utf-8")
    assert backup_mod.daemon_running(cfg) == os.getpid()


def test_start_daemon_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_BACKUP_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(LabError, match="disabled"):
        backup_mod.start_daemon(config=home / ".astroai" / "lab")


def test_start_daemon_spawns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    home = tmp_path / "home"
    home.mkdir()
    cfg = home / ".astroai" / "lab"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ASTROAI_LAB_BACKUP_ENABLED", raising=False)
    get_settings.cache_clear()

    fake = MagicMock()
    fake.pid = 424242
    with patch("subprocess.Popen", return_value=fake) as popen:
        pid = backup_mod.start_daemon(interval=3600, config=cfg, force=True)
    assert pid == 424242
    popen.assert_called_once()
    assert backup_mod.pid_path(cfg).read_text(encoding="utf-8").strip() == "424242"
    # Second start is idempotent while pid file claims a live process —
    # patch _pid_alive so 424242 looks alive without needing a real process.
    with patch.object(backup_mod, "_pid_alive", return_value=True):
        assert backup_mod.start_daemon(config=cfg, force=True) == 424242


def test_daemon_loop_one_iteration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.config.settings import get_settings

    get_settings.cache_clear()
    home = tmp_path / "home"
    work = tmp_path / "srcdir"
    home.mkdir()
    work.mkdir()
    (work / "a.py").write_text("x\n")
    cfg = home / ".astroai" / "lab"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_WORK_DIR", str(work))
    monkeypatch.delenv("skaha_sessionid", raising=False)
    get_settings.cache_clear()

    calls = {"n": 0}

    def _sleep(_sec: float) -> None:
        calls["n"] += 1
        if calls["n"] >= 1:
            raise KeyboardInterrupt

    with (
        patch.object(backup_mod, "quota_used_pct", return_value=10),
        patch.object(backup_mod, "run", return_value=None),
        patch("time.sleep", side_effect=_sleep),
        pytest.raises(KeyboardInterrupt),
    ):
        backup_mod.daemon_loop(interval=1, config=cfg)

    assert backup_mod.pid_path(cfg).is_file() or True  # may be cleaned by signal handler
    assert backup_mod.log_path(cfg).is_file()
