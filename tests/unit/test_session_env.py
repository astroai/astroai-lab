from __future__ import annotations

from pathlib import Path

import pytest

from canfar_lab.shell.session_env import export_shell, resolve_session_env


def test_resolve_session_env_prefers_scratch_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    work = tmp_path / "srcdir"
    work.mkdir()
    monkeypatch.setenv("TMP_SRC_DIR", str(work))
    monkeypatch.setenv("TMP_SCRATCH_DIR", str(scratch))
    monkeypatch.delenv("CANFAR_LAB_BIN_DIR", raising=False)

    env = resolve_session_env(ensure=True)
    assert env.canfar_lab_bin_dir == scratch / ".local" / "bin"
    assert str(scratch) in str(env.uv_cache_dir)


def test_export_shell_includes_canfar_lab_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("TMP_SRC_DIR", str(work))
    monkeypatch.delenv("TMP_SCRATCH_DIR", raising=False)

    out = export_shell(ensure=False)
    assert "export CANFAR_LAB_BIN_DIR=" in out
    assert "export CANFAR_LAB_RUNTIME_ROOT=" in out
    assert "export TMP_SRC_DIR=" in out
    assert "ASTROAI_" not in out
