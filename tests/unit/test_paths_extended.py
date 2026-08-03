from __future__ import annotations

from pathlib import Path

import pytest

from astroai_lab.core.paths import (
    find_arc_project_root,
    quota_used_pct,
    scratch_cache_root,
    user_bin_dir,
)
from astroai_lab.errors import LabError


def test_scratch_cache_root_with_scratch(tmp_path: Path) -> None:
    work = tmp_path / "work"
    scratch = tmp_path / "scratch"
    root = scratch_cache_root(work, scratch)
    assert str(scratch) in str(root)


def test_scratch_cache_root_without_scratch(tmp_path: Path) -> None:
    work = tmp_path / "work"
    root = scratch_cache_root(work, None)
    assert str(work) in str(root)


def test_quota_used_pct(tmp_path: Path) -> None:
    pct = quota_used_pct(tmp_path)
    assert pct is not None
    assert 0 <= pct <= 100


def test_quota_used_pct_missing() -> None:
    assert quota_used_pct(Path("/no/such/path")) is None


def test_user_bin_dir_prefers_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("SCRATCH", str(scratch))
    monkeypatch.delenv("ASTROAI_LAB_BIN_DIR", raising=False)
    assert user_bin_dir() == scratch / ".local" / "bin"


def test_user_bin_dir_never_falls_back_to_home_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without scratch/project/env, installs land in the runtime root, NOT ~/.local."""
    monkeypatch.chdir(tmp_path)  # no /arc mount reachable from the cwd
    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("WORK", str(work))
    monkeypatch.delenv("SCRATCH", raising=False)
    monkeypatch.delenv("ASTROAI_LAB_BIN_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROAI_LAB_RUNTIME_ROOT", str(work / ".runtime-test"))

    bin_dir = user_bin_dir()
    assert bin_dir == work / ".runtime-test" / "bin"
    assert str(bin_dir).startswith(str(work))
    assert not (home / ".local" / "bin").exists()


def test_user_bin_dir_runtime_root_default_without_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default runtime root (work/.runtime-<user>/bin) when no overrides at all."""
    monkeypatch.chdir(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("WORK", str(work))
    monkeypatch.delenv("SCRATCH", raising=False)
    monkeypatch.delenv("ASTROAI_LAB_BIN_DIR", raising=False)
    monkeypatch.delenv("ASTROAI_LAB_RUNTIME_ROOT", raising=False)

    bin_dir = user_bin_dir()
    assert bin_dir.name == "bin"
    assert ".runtime-" in str(bin_dir)
    assert str(bin_dir).startswith(str(work))


def test_find_arc_project_root_no_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert find_arc_project_root() is None


def test_find_arc_project_root_mounted() -> None:
    from unittest.mock import patch

    with patch("pathlib.Path.is_dir", side_effect=lambda: True):
        # We start from /arc/projects/demo/subdir
        start = Path("/arc/projects/demo/subdir")
        # is_dir mocked True → find_arc_project_root finds /arc/projects/demo
        assert find_arc_project_root(start) == Path("/arc/projects/demo")


def test_find_arc_project_root_not_found() -> None:
    from unittest.mock import patch

    with patch("pathlib.Path.is_dir", side_effect=lambda: True):
        assert find_arc_project_root(Path("/foo/bar")) is None


def test_lab_error_without_hint() -> None:
    err = LabError("plain error")
    assert str(err) == "plain error"
