"""Home-cache hygiene checks."""

from __future__ import annotations

from pathlib import Path

from astroai_lab.core.home_hygiene import check_home_cache_hygiene, hygiene_ok


def test_hygiene_ok_without_scratch(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # No writable scratch → no hard fail.
    assert hygiene_ok(home=home, scratch=tmp_path / "missing", env={})


def test_hygiene_fails_when_caches_under_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    (home / ".cache" / "pip").mkdir(parents=True)
    env = {
        "UV_CACHE_DIR": str(home / ".cache" / "uv"),
        "PIXI_CACHE_DIR": str(scratch / "pixi"),
        "PIP_CACHE_DIR": str(scratch / "pip"),
        "XDG_CACHE_HOME": str(home / ".cache"),
    }
    issues = check_home_cache_hygiene(home=home, scratch=scratch, env=env)
    assert any("UV_CACHE_DIR" in i.detail for i in issues)
    assert any(".cache/pip" in i.detail for i in issues)
    assert not hygiene_ok(home=home, scratch=scratch, env=env)


def test_hygiene_ok_with_scratch_exports(tmp_path: Path) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    env = {
        "UV_CACHE_DIR": str(scratch / "uv"),
        "PIXI_CACHE_DIR": str(scratch / "pixi"),
        "PIP_CACHE_DIR": str(scratch / "pip"),
        "XDG_CACHE_HOME": str(scratch / "xdg-cache"),
        "NPM_CONFIG_CACHE": str(scratch / "npm"),
        "HF_HOME": str(scratch / "hf"),
        "TORCH_HOME": str(scratch / "torch"),
        "TMPDIR": str(scratch / "tmp"),
        "CONDA_PKGS_DIRS": str(scratch / "conda"),
        "MAMBA_PKGS_DIRS": str(scratch / "conda"),
    }
    assert hygiene_ok(home=home, scratch=scratch, env=env)


def test_session_env_xdg_cache_on_scratch(tmp_path: Path, monkeypatch) -> None:
    from astroai_lab.shell.session_env import resolve_session_env

    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    work = tmp_path / "work"
    home.mkdir()
    scratch.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMP_SRC_DIR", str(work))
    monkeypatch.setenv("TMP_SCRATCH_DIR", str(scratch))
    for var in (
        "XDG_CACHE_HOME",
        "UV_CACHE_DIR",
        "PIP_CACHE_DIR",
        "PIXI_CACHE_DIR",
        "HF_HOME",
        "TORCH_HOME",
        "TMPDIR",
    ):
        monkeypatch.delenv(var, raising=False)
    env = resolve_session_env(ensure=False)
    assert str(env.xdg_cache_home).startswith(str(scratch))
    assert str(env.uv_cache_dir).startswith(str(scratch))
    exports = env.exports()
    assert exports["XDG_CACHE_HOME"].startswith(str(scratch))
