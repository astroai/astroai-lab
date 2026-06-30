from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from canfar_lab.core.storage import (
    ArcProjectInfo,
    QuotaLine,
    arc_project_statuses,
    collect_status_quotas,
    df_line,
    dir_size,
    home_breakdown,
    stage_data,
    sync_data,
    top_cpu_processes,
)
from canfar_lab.errors import LabError


def test_df_line(tmp_path: Path) -> None:
    line = df_line(tmp_path, "test")
    assert isinstance(line, QuotaLine)
    assert line.label == "test"


def test_df_line_missing() -> None:
    assert df_line(Path("/no/such/dir"), "x") is None


def test_dir_size_file(tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_text("12345")
    assert dir_size(f) == 5
    assert dir_size(tmp_path / "missing") == 0


def test_home_breakdown(tmp_path: Path) -> None:
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "data").write_text("x" * 50)
    rows = home_breakdown(tmp_path)
    assert any(r[0] == ".cache" for r in rows)


def test_top_cpu_processes() -> None:
    with patch("canfar_lab.utils.subprocess.run_capture", return_value="USER PID\nproc1\nproc2"):
        procs = top_cpu_processes(limit=1)
    assert len(procs) == 1


def test_top_cpu_processes_on_error() -> None:
    with patch("canfar_lab.utils.subprocess.run_capture", side_effect=LabError("fail")):
        assert top_cpu_processes() == []


def test_stage_data_target_exists(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    with pytest.raises(LabError, match="Target exists"):
        stage_data(src, dst)


def test_stage_data_dry_run(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    with patch("canfar_lab.core.storage.rsync_copy") as mock:
        stage_data(src, dst, dry_run=True)
    mock.assert_called_once()


def test_sync_data_outside_scratch(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    source = tmp_path / "elsewhere"
    source.mkdir()
    target = tmp_path / "target"
    with pytest.raises(LabError, match="not under scratch"):
        sync_data(source, target, scratch)


def test_sync_data_with_yes(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    source = tmp_path / "elsewhere"
    source.mkdir()
    target = tmp_path / "target"
    with patch("canfar_lab.core.storage.rsync_copy") as mock:
        sync_data(source, target, scratch, yes=True)
    mock.assert_called_once()


def test_rsync_missing_tool(tmp_path: Path) -> None:
    from canfar_lab.core.storage import rsync_copy

    with patch("canfar_lab.core.storage.shutil.which", return_value=None):
        with pytest.raises(LabError, match="rsync"):
            rsync_copy(tmp_path, tmp_path / "out")


def test_arc_project_statuses_marks_cwd() -> None:
    foo = Path("/arc/projects/foo")
    bar = Path("/arc/projects/bar")
    q = QuotaLine(label="foo", path=str(foo), used="1G", total="10G", free="9G", pct=10)
    with patch("canfar_lab.core.storage.find_arc_project_root", return_value=foo):
        with patch("canfar_lab.core.storage.list_arc_projects", return_value=[bar, foo]):
            with patch("canfar_lab.core.storage.df_line", return_value=q) as mock_df:
                with patch("canfar_lab.core.storage.read_acl_groups", return_value=[]):
                    with patch("canfar_lab.core.storage.project_access", return_value="rw"):
                        with patch("canfar_lab.core.storage.list_gms_groups", return_value=None):
                            active, rows, gms, vault = arc_project_statuses(gms=False, vault=False)
    assert gms is None
    assert vault is None
    assert active is not None
    assert active.name == "foo"
    assert active.is_cwd is True
    assert active.access == "rw"
    assert rows[0].name == "foo"
    mock_df.assert_any_call(foo, "foo", current=True)
    mock_df.assert_any_call(bar, "bar", current=False)


def test_collect_status_quotas_includes_home_and_scratch(tmp_path: Path) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    q = QuotaLine(label="x", path="p", used="1", total="2", free="1", pct=50)
    with patch("canfar_lab.core.storage.df_line", return_value=q):
        with patch("canfar_lab.core.storage.arc_project_statuses", return_value=(None, [], None, None)):
            rows = collect_status_quotas(home=home, scratch=scratch)
    assert len(rows) == 2
