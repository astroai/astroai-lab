from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from astroai_lab.core.team import init_team_project


def test_init_team_project_invalid_name() -> None:
    from astroai_lab.errors import LabError

    with pytest.raises(LabError, match="Invalid"):
        init_team_project("bad name!")


def test_init_team_project_no_arc() -> None:
    from astroai_lab.errors import LabError

    with patch.object(Path, "is_dir", return_value=False):
        with pytest.raises(LabError, match="/arc/projects"):
            init_team_project("mygroup")


def test_init_team_project_success(tmp_path: Path) -> None:
    fake_arc = tmp_path / "arc_projects"
    fake_arc.mkdir()

    with patch(
        "astroai_lab.core.team.Path",
        lambda *args: fake_arc if args == ("/arc/projects",) else Path(*args),
    ), patch("astroai_lab.core.team.subprocess.run") as mock_run:
        proj = init_team_project("mygroup", members=["alice", "bob"])
    assert proj == fake_arc / "mygroup"
    assert (proj / "data").is_dir()
    assert (proj / "results").is_dir()
    assert (proj / "env-saves").is_dir()
    # verify setfacl calls
    assert mock_run.call_count == 4


def test_project_layout(tmp_path: Path) -> None:
    from astroai_lab.core.team import project_layout

    proj = tmp_path / "mygroup"
    proj.mkdir()
    (proj / "data").mkdir()
    layout = project_layout(proj)
    assert "data/" in layout


def test_project_quota_line(tmp_path: Path) -> None:
    from astroai_lab.core.storage import QuotaLine
    from astroai_lab.core.team import project_quota_line

    with patch("astroai_lab.core.team.df_line") as mock_df:
        mock_df.return_value = QuotaLine(
            label="mygroup",
            path=str(tmp_path),
            used="100M",
            total="1G",
            free="900M",
            pct=10,
        )
        quota = project_quota_line(tmp_path, "mygroup")
    assert quota == "100M / 1G (10%) — 900M free"


def test_project_quota_line_none(tmp_path: Path) -> None:
    from astroai_lab.core.team import project_quota_line

    with patch("astroai_lab.core.team.df_line", return_value=None):
        assert project_quota_line(tmp_path, "mygroup") is None
