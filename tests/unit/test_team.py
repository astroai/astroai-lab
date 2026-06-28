from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from canfar_lab.core.team import init_team_project


def test_init_team_project_invalid_name() -> None:
    from canfar_lab.errors import LabError

    with pytest.raises(LabError, match="Invalid"):
        init_team_project("bad name!")


def test_init_team_project_no_arc() -> None:
    from canfar_lab.errors import LabError

    with patch.object(Path, "is_dir", return_value=False):
        with pytest.raises(LabError, match="/arc/projects"):
            init_team_project("mygroup")
