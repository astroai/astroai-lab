"""Periodic /srcdir → /arc/home work-tree backups."""

from __future__ import annotations

import json
import os
import shutil
import signal
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from astroai_lab import config_dir
from astroai_lab.core.paths import quota_used_pct, resolve_paths
from astroai_lab.errors import LabError
from astroai_lab.utils.subprocess import run

DEFAULT_INTERVAL_SEC = 3600
DEFAULT_QUOTA_SKIP_PCT = 90

# Large / rebuildable trees — keep source and .git metadata.
RSYNC_EXCLUDES: tuple[str, ...] = (
    ".pixi/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".tox/",
    ".cache/",
    "*.pyc",
    ".astroai-lab/workspaces/",
)


@dataclass
class BackupStatus:
    ok: bool
    source: str
    dest: str
    started_at: str
    finished_at: str
    duration_sec: float
    message: str = ""
    skipped: bool = False
    bytes_approx: int | None = None


def session_id() -> str:
    return (os.environ.get("skaha_sessionid") or "").strip() or "local"


def default_backup_root(home: Path | None = None) -> Path:
    raw = os.environ.get("ASTROAI_LAB_BACKUP_DIR", "").strip()
    if raw:
        return Path(raw)
    return (home or Path.home()) / ".astroai" / "lab" / "backups"


def backup_dest(work_dir: Path | None = None, *, root: Path | None = None) -> Path:
    base = root or default_backup_root()
    return base / session_id()


def status_path(config: Path | None = None) -> Path:
    return (config or config_dir()) / "backup-status.json"


def pid_path(config: Path | None = None) -> Path:
    return (config or config_dir()) / "backup.pid"


def log_path(config: Path | None = None) -> Path:
    return (config or config_dir()) / "backup.log"


def backup_enabled() -> bool:
    raw = os.environ.get("ASTROAI_LAB_BACKUP_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def backup_interval_sec() -> int:
    raw = os.environ.get("ASTROAI_LAB_BACKUP_INTERVAL", "").strip()
    if not raw:
        return DEFAULT_INTERVAL_SEC
    try:
        value = int(raw)
    except ValueError as exc:
        raise LabError(
            f"Invalid ASTROAI_LAB_BACKUP_INTERVAL: {raw}",
            hint="Use seconds as an integer (e.g. 3600).",
        ) from exc
    if value < 60:
        raise LabError(
            f"ASTROAI_LAB_BACKUP_INTERVAL too small: {value}",
            hint="Minimum interval is 60 seconds.",
        )
    return value


def load_status(config: Path | None = None) -> BackupStatus | None:
    path = status_path(config)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return BackupStatus(**data)
    except TypeError:
        return None


def write_status(status: BackupStatus, config: Path | None = None) -> None:
    path = status_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(status), indent=2) + "\n", encoding="utf-8")


def _home_for_quota(dest: Path) -> Path:
    home = Path.home()
    try:
        dest.resolve().relative_to(home.resolve())
        return home
    except ValueError:
        return dest if dest.is_dir() else dest.parent


def run_backup(
    *,
    source: Path | None = None,
    dest: Path | None = None,
    dry_run: bool = False,
    yes: bool = False,
    config: Path | None = None,
) -> BackupStatus:
    """One-shot rsync of the work directory to persistent home backups."""
    paths = resolve_paths()
    src = (source or paths.work_dir).resolve()
    target = (dest or backup_dest(src)).resolve()
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()

    if not src.is_dir():
        status = BackupStatus(
            ok=False,
            source=str(src),
            dest=str(target),
            started_at=started.strftime("%Y%m%dT%H%M%SZ"),
            finished_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            duration_sec=0.0,
            message=f"Source not found: {src}",
        )
        write_status(status, config)
        raise LabError(status.message)

    quota_pct = quota_used_pct(_home_for_quota(target))
    if quota_pct is not None and quota_pct >= DEFAULT_QUOTA_SKIP_PCT and not yes:
        status = BackupStatus(
            ok=False,
            source=str(src),
            dest=str(target),
            started_at=started.strftime("%Y%m%dT%H%M%SZ"),
            finished_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            duration_sec=time.monotonic() - t0,
            message=f"Home quota {quota_pct}% — backup skipped (use --yes to force)",
            skipped=True,
        )
        write_status(status, config)
        return status

    if dry_run:
        status = BackupStatus(
            ok=True,
            source=str(src),
            dest=str(target),
            started_at=started.strftime("%Y%m%dT%H%M%SZ"),
            finished_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            duration_sec=time.monotonic() - t0,
            message="dry-run",
        )
        return status

    target.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync") is None:
        raise LabError("rsync is required.", hint="Install rsync on the session image.")

    cmd = ["rsync", "-a", "--delete"]
    for pattern in RSYNC_EXCLUDES:
        cmd.append(f"--exclude={pattern}")
    cmd.extend([f"{src}/", f"{target}/"])

    try:
        run(cmd, quiet=True)
    except LabError as exc:
        status = BackupStatus(
            ok=False,
            source=str(src),
            dest=str(target),
            started_at=started.strftime("%Y%m%dT%H%M%SZ"),
            finished_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            duration_sec=time.monotonic() - t0,
            message=str(exc),
        )
        write_status(status, config)
        raise

    finished = datetime.now(timezone.utc)
    status = BackupStatus(
        ok=True,
        source=str(src),
        dest=str(target),
        started_at=started.strftime("%Y%m%dT%H%M%SZ"),
        finished_at=finished.strftime("%Y%m%dT%H%M%SZ"),
        duration_sec=time.monotonic() - t0,
        message="ok",
    )
    write_status(status, config)
    return status


def restore_backup(
    *,
    source: Path | None = None,
    dest: Path | None = None,
    dry_run: bool = False,
    yes: bool = False,
) -> Path:
    """Rsync a backup mirror back into the work directory."""
    paths = resolve_paths()
    src = (source or backup_dest()).resolve()
    target = (dest or paths.work_dir).resolve()
    if not src.is_dir():
        raise LabError(
            f"Backup not found: {src}",
            hint="astroai-lab backup run",
        )
    if target.exists() and any(target.iterdir()) and not yes and not dry_run:
        raise LabError(
            f"Target is not empty: {target}",
            hint="astroai-lab backup restore --yes",
        )
    if dry_run:
        return target
    target.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync") is None:
        raise LabError("rsync is required.", hint="Install rsync on the session image.")
    cmd = ["rsync", "-a"]
    for pattern in RSYNC_EXCLUDES:
        cmd.append(f"--exclude={pattern}")
    cmd.extend([f"{src}/", f"{target}/"])
    run(cmd, quiet=True)
    return target


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def daemon_running(config: Path | None = None) -> int | None:
    path = pid_path(config)
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if _pid_alive(pid):
        return pid
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def stop_daemon(config: Path | None = None) -> bool:
    pid = daemon_running(config)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        pid_path(config).unlink(missing_ok=True)
    except OSError:
        pass
    return True


def daemon_loop(*, interval: int | None = None, config: Path | None = None) -> None:
    """Blocking loop used by the background backup process."""
    import sys

    interval_sec = interval if interval is not None else backup_interval_sec()
    cfg = config or config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    pid_path(cfg).write_text(f"{os.getpid()}\n", encoding="utf-8")
    log = log_path(cfg)

    def _on_signal(_signum: int, _frame: object) -> None:
        try:
            pid_path(cfg).unlink(missing_ok=True)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    with log.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{datetime.now(timezone.utc).isoformat()} daemon start "
            f"pid={os.getpid()} interval={interval_sec}\n"
        )
        fh.flush()
        # Immediate first pass, then sleep between subsequent runs.
        while True:
            try:
                status = run_backup(config=cfg)
                fh.write(
                    f"{datetime.now(timezone.utc).isoformat()} "
                    f"ok={status.ok} skipped={status.skipped} {status.message}\n"
                )
            except Exception as exc:  # noqa: BLE001 — keep daemon alive
                fh.write(f"{datetime.now(timezone.utc).isoformat()} error: {exc}\n")
            fh.flush()
            time.sleep(interval_sec)


def start_daemon(
    *,
    interval: int | None = None,
    config: Path | None = None,
    force: bool = False,
) -> int:
    """Spawn a background backup loop. Returns daemon pid."""
    import subprocess
    import sys

    if not backup_enabled() and not force:
        raise LabError(
            "Backups disabled (ASTROAI_LAB_BACKUP_ENABLED=false).",
            hint="Unset or set ASTROAI_LAB_BACKUP_ENABLED=true",
        )
    existing = daemon_running(config)
    if existing is not None:
        return existing

    interval_sec = interval if interval is not None else backup_interval_sec()
    cfg = config or config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    log = log_path(cfg)

    cmd = [
        sys.executable,
        "-m",
        "astroai_lab",
        "backup",
        "loop",
        f"--interval={interval_sec}",
    ]
    with log.open("a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=str(Path.home()),
        )
    pid_path(cfg).write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc.pid
