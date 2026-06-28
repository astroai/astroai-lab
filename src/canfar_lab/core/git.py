from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run_capture


@dataclass
class GitStatus:
    in_repo: bool
    branch: str | None
    remote: str | None
    uncommitted: bool
    ahead: int = 0


def git_status(cwd: Path | None = None) -> GitStatus:
    root = cwd or Path.cwd()
    try:
        run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)
    except LabError:
        return GitStatus(in_repo=False, branch=None, remote=None, uncommitted=False)

    branch = run_capture(["git", "branch", "--show-current"], cwd=root) or None
    try:
        remote = run_capture(["git", "remote", "get-url", "origin"], cwd=root)
    except LabError:
        remote = None

    uncommitted = False
    try:
        run_capture(["git", "rev-parse", "--verify", "HEAD"], cwd=root)
        run_capture(["git", "diff-index", "--quiet", "HEAD", "--"], cwd=root)
    except LabError:
        uncommitted = True

    return GitStatus(
        in_repo=True,
        branch=branch,
        remote=remote,
        uncommitted=uncommitted,
    )


def git_push(cwd: Path | None = None) -> None:
    from canfar_lab.utils.subprocess import run

    root = cwd or Path.cwd()
    run(["git", "push"], cwd=root)


def git_init_and_commit(target: Path, message: str = "Initial commit") -> None:
    from canfar_lab.utils.subprocess import run

    if not (target / ".git").exists():
        run(["git", "init", "-q"], cwd=target)
    run(["git", "add", "-A"], cwd=target)
    try:
        run(["git", "commit", "-m", message, "--quiet"], cwd=target)
    except LabError:
        pass
