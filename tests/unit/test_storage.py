from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from astroai_lab.core.storage import rsync_copy
from astroai_lab.errors import LabError


def test_rsync_copy_dry_run(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "file.txt").write_text("data")
    with patch("astroai_lab.core.storage.run") as mock_run:
        rsync_copy(src, dst, dry_run=True)
    mock_run.assert_called_once()
    assert "--dry-run" in mock_run.call_args[0][0]


def test_stage_data_raises_missing(tmp_path: Path) -> None:
    from astroai_lab.core.storage import stage_data

    with pytest.raises(LabError):
        stage_data(tmp_path / "missing", tmp_path / "out", dry_run=True)
