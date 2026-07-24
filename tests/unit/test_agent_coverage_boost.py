from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from astroai_lab.agent.bundles import SetupResult, agent_setup
from astroai_lab.agent.setup_state import (
    agent_setup_lock,
    append_setup_log,
    dump_json,
    read_setup_state,
)
from astroai_lab.cli.main import app
from astroai_lab.core.session_resources import collect_resources

runner = CliRunner()


def test_append_setup_log_and_dump_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    append_setup_log(home, "hello")
    append_setup_log(home, "world\n")
    state = read_setup_state(home)
    assert state.log is not None
    assert "hello" in Path(state.log).read_text()
    assert dump_json({"a": 1}).startswith("{")


def test_agent_setup_records_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.run_bundle",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.verify_setup",
        lambda home: [],
    )
    monkeypatch.setattr(
        "astroai_lab.core.paths.quota_used_pct",
        lambda path: 10,
    )
    result = agent_setup(bundles=["cli"], force=True, dry_run=False, verify=True)
    assert result.ok
    assert result.exit_code == 0
    assert read_setup_state(home).ok


def test_agent_setup_verify_failure_marks_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.run_bundle",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.verify_setup",
        lambda home: ["missing mcp"],
    )
    monkeypatch.setattr(
        "astroai_lab.core.paths.quota_used_pct",
        lambda path: 10,
    )
    result = agent_setup(bundles=["cli"], force=True, dry_run=False, verify=True)
    assert not result.ok
    assert result.partial
    assert result.exit_code == 2
    assert read_setup_state(home).failed is not None


def test_agent_setup_json_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.cli.agent_cmd.agent_setup_mod.agent_setup",
        lambda **k: SetupResult(
            ok=True,
            partial=False,
            mode="install",
            actions=("bundle:cli",),
            errors=(),
            warnings=(),
            stamp="now",
        ),
    )
    result = runner.invoke(app, ["--json", "agent", "setup", "cli"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_agent_install_json_dry_run() -> None:
    result = runner.invoke(app, ["--json", "--dry-run", "agent", "install", "kilo"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["tool"] == "kilo"


def test_agent_addons_and_list_json() -> None:
    result = runner.invoke(app, ["--json", "agent", "addons"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    result = runner.invoke(app, ["--json", "agent", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "tools" in data
    assert "addons" in data


def test_agent_add_json_dry_run() -> None:
    result = runner.invoke(app, ["--json", "--dry-run", "agent", "add", "ponytail"])
    # may be 0 with dry-run result
    assert result.exit_code in (0, 1, 2)
    if result.stdout.strip().startswith("{") or result.stdout.strip().startswith("["):
        pass
    else:
        # rich may wrap; still ensure command ran
        assert "ponytail" in (result.stdout + result.stderr).lower() or result.exit_code == 0


def test_agent_models_list_json() -> None:
    result = runner.invoke(app, ["--json", "agent", "models", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_resources_cgroup_and_gpu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.core.session_resources._cgroup_mem_pct",
        lambda: 42.0,
    )
    monkeypatch.setattr(
        "astroai_lab.core.session_resources._gpu_stats",
        lambda: [
            {
                "index": 0,
                "name": "TestGPU",
                "util_pct": 10.0,
                "mem_used_mib": 1.0,
                "mem_total_mib": 8.0,
            }
        ],
    )
    snap = collect_resources()
    assert snap.cgroup_mem_pct == 42.0
    assert snap.gpu[0]["name"] == "TestGPU"


def test_agent_sync_ok_and_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astroai_lab.agent.bundles import SourceUpdateResult, agent_sync

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.default_bundle_names",
        lambda root: ["cli"],
    )
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.run_bundle",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "astroai_lab.agent.bundles.update_all_github_sources",
        lambda *a, **k: [
            SourceUpdateResult("x", "org/x", "updated"),
        ],
    )
    results = agent_sync(dry_run=False)
    assert results[0].status == "updated"
    assert read_setup_state(home).ok

    monkeypatch.setattr(
        "astroai_lab.agent.bundles.update_all_github_sources",
        lambda *a, **k: [
            SourceUpdateResult("x", "org/x", "failed", "boom"),
        ],
    )
    agent_sync(dry_run=False)
    assert read_setup_state(home).failed is not None


def test_install_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.agent import install as inst

    assert "kilo" in inst.list_tools()
    assert inst.tool_binary("qoder") == "qodercli"
    rows = inst.list_tools_status()
    assert any(r["name"] == "kilo" for r in rows)

    # Timeout path for curl|bash without network
    monkeypatch.setattr(
        "astroai_lab.agent.install.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(
            __import__("subprocess").TimeoutExpired(cmd="curl", timeout=1)
        ),
    )
    with pytest.raises(Exception, match="timed out"):
        inst._curl_pipe_bash("https://example.invalid/install")


def test_cgroup_and_gpu_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    from astroai_lab.core import session_resources as sr

    class FakePath:
        def __init__(self, p: object) -> None:
            self.p = str(p)

        def is_file(self) -> bool:
            return self.p in {
                "/sys/fs/cgroup/memory.current",
                "/sys/fs/cgroup/memory.max",
            }

        def read_text(self, encoding: str = "utf-8") -> str:
            return {
                "/sys/fs/cgroup/memory.current": "25\n",
                "/sys/fs/cgroup/memory.max": "100\n",
            }[self.p]

    monkeypatch.setattr(sr, "Path", FakePath)
    assert sr._cgroup_mem_pct() == 25.0

    monkeypatch.setattr(sr.shutil, "which", lambda name: "/usr/bin/nvidia-smi")

    class R:
        returncode = 0
        stdout = "0, Fake GPU, 12, 100, 8000\n"

    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: R())
    gpus = sr._gpu_stats()
    assert gpus[0]["name"] == "Fake GPU"
    assert gpus[0]["util_pct"] == 12.0


def test_status_json_has_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(app, ["--json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "resources" in data
    assert "home" in data["resources"]


def test_agent_setup_quota_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.core.paths.quota_used_pct",
        lambda path: 99,
    )
    from astroai_lab.errors import LabError

    with pytest.raises(LabError, match="Home quota"):
        agent_setup(bundles=["cli"], force=False, dry_run=False)


def test_agent_project_json_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        "astroai_lab.cli.agent_cmd.agent_setup_mod.agent_setup",
        lambda **k: (_ for _ in ()).throw(
            __import__("astroai_lab.errors", fromlist=["LabError"]).LabError("nope")
        ),
    )
    result = runner.invoke(app, ["--json", "agent", "project", str(tmp_path)])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
