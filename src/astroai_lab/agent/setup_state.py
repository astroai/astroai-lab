"""Agent setup lock, stamp, failed marker, and machine-readable report."""

from __future__ import annotations

import contextlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.errors import LabError

GIT_TIMEOUT_SEC = int(os.environ.get("ASTROAI_LAB_AGENT_GIT_TIMEOUT", "120"))
INSTALL_TIMEOUT_SEC = int(os.environ.get("ASTROAI_LAB_AGENT_INSTALL_TIMEOUT", "300"))
LOCK_TIMEOUT_SEC = int(os.environ.get("ASTROAI_LAB_AGENT_LOCK_TIMEOUT", "30"))


def lab_state_dir(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / ".astroai" / "lab"


def stamp_path(home: Path | None = None) -> Path:
    return lab_state_dir(home) / "agent-setup-stamp"


def failed_path(home: Path | None = None) -> Path:
    return lab_state_dir(home) / "agent-setup-failed"


def log_path(home: Path | None = None) -> Path:
    return lab_state_dir(home) / "agent-setup.log"


def lock_path(home: Path | None = None) -> Path:
    return lab_state_dir(home) / "agent-setup.lock"


@dataclass
class SetupState:
    stamp: str | None
    failed: str | None
    log: str | None
    ok: bool
    needs_retry: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_setup_state(home: Path | None = None) -> SetupState:
    home = home or Path.home()
    stamp = stamp_path(home)
    failed = failed_path(home)
    log = log_path(home)
    stamp_text = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else None
    failed_text = failed.read_text(encoding="utf-8").strip() if failed.is_file() else None
    log_exists = log.is_file()
    ok = stamp_text is not None and failed_text is None
    needs_retry = stamp_text is None or failed_text is not None
    return SetupState(
        stamp=stamp_text,
        failed=failed_text,
        log=str(log) if log_exists else None,
        ok=ok,
        needs_retry=needs_retry,
    )


def record_setup_ok(home: Path | None = None, *, mode: str = "install") -> None:
    home = home or Path.home()
    state = lab_state_dir(home)
    state.mkdir(parents=True, exist_ok=True)
    ver = "unknown"
    version_file = bundle_root() / "VERSION"
    if version_file.is_file():
        ver = version_file.read_text(encoding="utf-8").strip()
    stamp_path(home).write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        + f" bundle={ver} mode={mode}\n",
        encoding="utf-8",
    )
    failed_path(home).unlink(missing_ok=True)


def record_setup_failed(
    home: Path | None = None,
    *,
    exit_code: int = 1,
    detail: str = "",
) -> None:
    home = home or Path.home()
    state = lab_state_dir(home)
    state.mkdir(parents=True, exist_ok=True)
    line = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        + f" exit={exit_code}"
        + (f" {detail}" if detail else "")
        + "\n"
    )
    failed_path(home).write_text(line, encoding="utf-8")


def append_setup_log(home: Path | None, text: str) -> None:
    home = home or Path.home()
    path = log_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")


@contextmanager
def agent_setup_lock(
    home: Path | None = None,
    *,
    timeout: float | None = None,
) -> Iterator[None]:
    """Exclusive lock for agent setup / wizard actions."""
    home = home or Path.home()
    timeout = LOCK_TIMEOUT_SEC if timeout is None else timeout
    path = lock_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    my_pid = os.getpid()
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"{my_pid} {time.time()}\n".encode())
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                if _lock_is_stale(path):
                    path.unlink(missing_ok=True)
                    continue
                raise LabError(
                    "Another agent setup is already running",
                    hint=f"Wait or remove stale lock: {path}",
                )
            time.sleep(0.25)
    try:
        yield
    finally:
        # Only remove the lock if we still own it (avoid deleting a stealer's lock).
        try:
            text = path.read_text(encoding="utf-8").strip()
            owner = text.split()[0] if text else ""
            if owner == str(my_pid):
                path.unlink(missing_ok=True)
        except OSError:
            pass
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


def _lock_holder_alive(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8").strip().split()
        if not raw:
            return False
        pid = int(raw[0])
    except (OSError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, not ours
    return True


def _lock_is_stale(path: Path) -> bool:
    """Stale when the recorded holder PID is dead or the lock file is unreadable."""
    if not path.is_file():
        return True
    return not _lock_holder_alive(path)


def build_agent_report(home: Path | None = None) -> dict[str, Any]:
    """One-shot JSON report for wizard / automation."""
    import shutil

    from astroai_lab.agent.bundles import verify_setup
    from astroai_lab.core.session_resources import collect_resources

    home = home or Path.home()
    state = read_setup_state(home)
    issues = verify_setup(home)
    agents = []
    for name, binary, config_path in (
        ("opencode", "opencode", home / ".config" / "opencode" / "opencode.json"),
        ("claude", "claude", home / ".claude.json"),
        ("goose", "goose", home / ".config" / "goose" / "config.yaml"),
        ("kilo", "kilo", home / ".config" / "kilo" / "kilo.jsonc"),
        ("codex", "codex", home / ".codex" / "config.toml"),
        ("copilot", "copilot", home / ".copilot" / "mcp-config.json"),
        ("cline", "cline", home / ".config" / "canfar" / "lab" / "cline-free.md"),
        ("qoder", "qodercli", home / ".qoder" / "settings.json"),
        ("agent", "agent", home / ".cursor" / "mcp.json"),
    ):
        agents.append(
            {
                "agent": name,
                "binary": shutil.which(binary) is not None,
                "config": config_path.is_file(),
                "config_path": str(config_path),
            }
        )
    return {
        "ok": state.ok and not issues,
        "setup": state.to_dict(),
        "issues": issues,
        "agents": agents,
        "resources": collect_resources().to_dict(),
        "log_tail": _log_tail(home, n=40),
    }


def _log_tail(home: Path, *, n: int = 40) -> str:
    path = log_path(home)
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def dump_json(data: Any) -> str:
    return json.dumps(data, indent=2) + "\n"
