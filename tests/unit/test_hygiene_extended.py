from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from canfar_lab.core.hygiene import (
    CleanTarget,
    apply_clean,
    collect_cache_targets,
    collect_home_targets,
    format_bytes,
    prune_uv_cache,
)


def test_format_bytes() -> None:
    assert "B" in format_bytes(1024)


def test_collect_home_ml_and_xdg(tmp_path: Path) -> None:
    home = tmp_path
    (home / ".cache" / "torch").mkdir(parents=True)
    (home / ".local" / "share" / "Trash").mkdir(parents=True)
    targets = collect_home_targets(home, stale_pkg=False, ml=True, hf=False, xdg_junk=True)
    labels = {t.label for t in targets}
    assert ".cache/torch" in labels


def test_collect_home_hf(tmp_path: Path) -> None:
    home = tmp_path
    (home / ".cache" / "huggingface").mkdir(parents=True)
    targets = collect_home_targets(home, stale_pkg=False, ml=False, hf=True, xdg_junk=False)
    assert any(t.label == ".cache/huggingface" for t in targets)


def test_collect_home_skips_protected(tmp_path: Path) -> None:
    home = tmp_path
    (home / ".ssh").mkdir()
    (home / ".ssh" / "id_rsa").write_text("secret")
    targets = collect_home_targets(home, stale_pkg=False, ml=False, hf=False, xdg_junk=True)
    assert not any(".ssh" in t.label for t in targets)


def test_apply_clean_deletes(tmp_path: Path) -> None:
    target = tmp_path / "junk"
    target.mkdir()
    (target / "f").write_text("x")
    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
    freed = apply_clean([CleanTarget(path=target, label="junk", bytes=size)], dry_run=False)
    assert freed > 0
    assert not target.exists()


def test_collect_cache_targets_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "pip-cache"
    cache.mkdir()
    (cache / "wheel").write_text("x")
    monkeypatch.setenv("PIP_CACHE_DIR", str(cache))
    targets = collect_cache_targets(
        pip=True, uv_cache=False, npm=False, pixi=False, conda=False, hf=False
    )
    assert len(targets) == 1


def test_prune_uv_cache_dry_run() -> None:
    with patch("canfar_lab.core.hygiene.shutil.which", return_value="/usr/bin/uv"):
        with patch("canfar_lab.core.hygiene.run") as mock_run:
            prune_uv_cache(dry_run=True)
    mock_run.assert_not_called()


def test_prune_uv_cache_runs() -> None:
    with patch("canfar_lab.core.hygiene.shutil.which", return_value="/usr/bin/uv"):
        with patch("canfar_lab.core.hygiene.run") as mock_run:
            prune_uv_cache(dry_run=False)
    mock_run.assert_called_once_with(["uv", "cache", "prune"])
