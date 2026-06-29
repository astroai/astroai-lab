from __future__ import annotations

from canfar_lab import ui


def _combined(capsys) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def test_doctor_human(capsys) -> None:
    report = ui.DoctorReport(
        work_dir="/srcdir",
        scratch_dir="/scratch",
        save_dir="/home/.canfar/lab/saves",
        config_dir="/home/.canfar/lab",
        home="/home",
        user_bin="/scratch/.local/bin",
        npm_prefix="/scratch/.local",
        runtime_root="/scratch/.runtime-user",
        arc_projects="/arc/projects",
        pixi_cache_dir="/scratch/.cache/pixi",
        uv_cache_dir="/scratch/.cache/uv",
        home_quota_pct=85,
        tools={"git": True, "pixi": False},
    )
    ui.doctor_human(report)
    combined = _combined(capsys)
    assert "srcdir" in combined or "doctor" in combined.lower()


def test_env_list_table_empty(capsys) -> None:
    ui.env_list_table([])
    assert "No saved environments" in _combined(capsys)


def test_env_list_table_with_rows(capsys) -> None:
    ui.env_list_table([{"name": "mylab", "kind": "pixi", "saved_at": "t", "path": "/save/mylab"}])
    assert "mylab" in _combined(capsys)


def test_status_human(capsys) -> None:
    from canfar_lab.core.storage import QuotaLine

    quotas = [QuotaLine(label="home", used="1G", total="10G", pct=90)]
    ui.status_human(quotas, [(".cache", "1M", "caches")], "hint", ["proc1"])
    assert "status" in _combined(capsys).lower()


def test_print_helpers(capsys) -> None:
    ui.print_error("bad\n  hint `cmd`")
    ui.print_ok("good `cmd`")
    ui.print_hint("hint `cmd`")
    ui.print_info("info `cmd`")
    ui.print_warn("warn `cmd`")
    ui.print_json({"a": 1})
    combined = _combined(capsys)
    assert "bad" in combined
    assert "cmd" in combined
    assert '"a"' in combined


def test_progress_task_quiet() -> None:
    with ui.progress_task("test", quiet=True):
        pass


def test_format_text() -> None:
    assert "[bold #ffaf00]mycmd[/bold #ffaf00]" in ui._format_text("`mycmd`")
    assert "[bold #00d7ff]git status[/bold #00d7ff]" in ui._format_text("  git status")
