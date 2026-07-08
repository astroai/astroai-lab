from __future__ import annotations

import subprocess
from pathlib import Path

from canfar_lab.errors import LabError


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    quiet: bool = False,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    kwargs: dict = {"cwd": cwd, "check": True, "text": True}
    if env is not None:
        kwargs["env"] = env
    if quiet or capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError as exc:
        raise LabError(
            f"Required command not found: {cmd[0]}",
            hint=f"Install {cmd[0]} or check your PATH",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        msg = f"Command failed: {' '.join(cmd)} (exit {exc.returncode})"
        if detail:
            msg = f"{msg}\n{detail}"
        raise LabError(msg) from exc


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    quiet: bool = False,
    env: dict[str, str] | None = None,
) -> None:
    run_cmd(cmd, cwd=cwd, quiet=quiet, env=env)


def run_capture(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    result = run_cmd(cmd, cwd=cwd, capture=True, env=env)
    assert result is not None
    return (result.stdout or "").strip()
