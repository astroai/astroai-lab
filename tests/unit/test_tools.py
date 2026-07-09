from __future__ import annotations

from pathlib import Path

from canfar_lab.core.tools import (
    CheckItem,
    checks_ok,
    doctor_tools,
    inventory_tools,
    paths_dict,
    run_checks,
    tool_info,
)


def test_tool_info_missing() -> None:
    info = tool_info("definitely-not-a-real-canfar-tool-xyz")
    assert info.available is False
    assert info.path is None


def test_tool_info_python() -> None:
    info = tool_info("python3", ("--version",))
    assert info.available is True
    assert info.path is not None


def test_inventory_tools_nonempty() -> None:
    tools = inventory_tools()
    assert len(tools) >= 10
    names = {t.name for t in tools}
    assert "git" in names
    assert "canfar-lab" in names


def test_doctor_tools_keys() -> None:
    tools = doctor_tools()
    assert "git" in tools
    assert "pixi" in tools
    assert isinstance(tools["git"], bool)


def test_paths_dict(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    work = home / "work"
    scratch = home / "scratch"
    home.mkdir()
    work.mkdir()
    scratch.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_WORK_DIR", str(work))
    monkeypatch.setenv("CANFAR_LAB_SCRATCH_DIR", str(scratch))
    data = paths_dict()
    assert data["work_dir"] == str(work)
    assert data["scratch_dir"] == str(scratch)
    assert data["home"] == str(home)
    assert data["cwd"]


def test_run_checks_ok_when_writable(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    work = home / "work"
    scratch = home / "scratch"
    home.mkdir()
    work.mkdir()
    scratch.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_WORK_DIR", str(work))
    monkeypatch.setenv("CANFAR_LAB_SCRATCH_DIR", str(scratch))
    items = run_checks()
    by_name = {i.name: i for i in items}
    assert by_name["work_dir"].ok
    assert by_name["scratch_dir"].ok


def test_checks_ok_strict() -> None:
    items = [
        CheckItem("work_dir", True, "ok"),
        CheckItem("pixi", True, "missing (recommended)"),
    ]
    assert checks_ok(items, strict=False) is True
    assert checks_ok(items, strict=True) is False
