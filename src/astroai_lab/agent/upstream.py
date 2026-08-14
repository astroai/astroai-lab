"""GitHub upstream skill sync (clone / refresh / install)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.utils.json_utils import read_json


@dataclass(frozen=True)
class SourceUpdateResult:
    name: str
    repo: str
    status: str
    detail: str = ""


def _upstream_cache_root(home: Path, repo: str) -> Path:
    return home / ".cache" / "astroai-lab" / "upstream-skills" / repo.replace("/", "_")


def upstream_cache_path(home: Path, repo: str) -> Path:
    return _upstream_cache_root(home, repo)


def _git_run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    from astroai_lab.agent.setup_state import GIT_TIMEOUT_SEC

    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout="",
            stderr=f"git timed out after {GIT_TIMEOUT_SEC}s: {exc}",
        )


def _clone_upstream_repo(cache_root: Path, repo: str, paths: str | list[str]) -> tuple[str, str]:
    path_list = [paths] if isinstance(paths, str) else list(paths)
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    clone = _git_run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            f"https://github.com/{repo}.git",
            str(cache_root),
        ]
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout or "clone failed").strip()
        return "failed", detail
    # --no-cone allows file paths (e.g. .cursor/rules/ponytail.mdc), not only dirs.
    sparse = _git_run(
        ["git", "-C", str(cache_root), "sparse-checkout", "set", "--no-cone", *path_list]
    )
    if sparse.returncode != 0:
        detail = (sparse.stderr or sparse.stdout or "sparse-checkout failed").strip()
        return "failed", detail
    return "cloned", repo


def _refresh_upstream_repo(cache_root: Path, repo: str, paths: str | list[str]) -> tuple[str, str]:
    path_list = [paths] if isinstance(paths, str) else list(paths)
    if not (cache_root / ".git").is_dir():
        return _clone_upstream_repo(cache_root, repo, path_list)
    fetch = _git_run(["git", "-C", str(cache_root), "fetch", "--depth", "1", "origin", "HEAD"])
    if fetch.returncode != 0:
        shutil.rmtree(cache_root)
        return _clone_upstream_repo(cache_root, repo, path_list)
    reset = _git_run(["git", "-C", str(cache_root), "reset", "--hard", "FETCH_HEAD"])
    if reset.returncode != 0:
        detail = (reset.stderr or reset.stdout or "reset failed").strip()
        return "failed", detail
    sparse = _git_run(
        ["git", "-C", str(cache_root), "sparse-checkout", "set", "--no-cone", *path_list]
    )
    if sparse.returncode != 0:
        detail = (sparse.stderr or sparse.stdout or "sparse-checkout failed").strip()
        return "failed", detail
    return "updated", repo


def list_github_sources(root: Path | None = None) -> list[dict[str, str]]:
    sources = (root or bundle_root()) / "skills-sources.json"
    if not sources.is_file():
        return []
    data = read_json(sources)
    rows: list[dict[str, str]] = []
    for item in data.get("upstream_skills", []):
        rows.append(
            {
                "name": item["name"],
                "repo": item["repo"],
                "path": item["path"],
                "homepage": item.get("homepage", f"https://github.com/{item['repo']}"),
            }
        )
    return rows


def update_github_source(
    home: Path,
    name: str,
    repo: str,
    path: str,
    *,
    force: bool,
    dry_run: bool,
) -> SourceUpdateResult:
    from astroai_lab.agent.agent_targets import AGENT_SKILL_DIRS

    dests = [home / rel / name for rel in AGENT_SKILL_DIRS.values()]
    pending = [d for d in dests if force or not (d / "SKILL.md").is_file()]
    if not pending:
        return SourceUpdateResult(name, repo, "skipped", "already installed")

    if dry_run:
        return SourceUpdateResult(name, repo, "dry-run", path)

    cache_root = _upstream_cache_root(home, repo)
    status, detail = _refresh_upstream_repo(cache_root, repo, path)
    if status == "failed":
        return SourceUpdateResult(name, repo, status, detail)

    src = cache_root / path
    if not (src / "SKILL.md").is_file():
        return SourceUpdateResult(name, repo, "failed", f"missing SKILL.md at {path}")

    for dst in pending:
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
    return SourceUpdateResult(name, repo, status, path)


def update_all_github_sources(
    home: Path | None = None,
    *,
    force: bool = True,
    dry_run: bool = False,
) -> list[SourceUpdateResult]:
    root = bundle_root()
    home = home or Path.home()
    results: list[SourceUpdateResult] = []
    for item in list_github_sources(root):
        results.append(
            update_github_source(
                home,
                item["name"],
                item["repo"],
                item["path"],
                force=force,
                dry_run=dry_run,
            )
        )
    return results


def install_upstream_skill(
    root: Path,
    home: Path,
    name: str,
    repo: str,
    path: str,
    *,
    force: bool,
    dry_run: bool,
) -> bool:
    result = update_github_source(home, name, repo, path, force=force, dry_run=dry_run)
    return result.status in {"cloned", "updated", "dry-run"}


def install_upstream_skills(root: Path, home: Path, *, force: bool, dry_run: bool) -> int:
    return sum(
        1
        for r in update_all_github_sources(home, force=force, dry_run=dry_run)
        if r.status in {"cloned", "updated", "dry-run"}
    )
