"""Unit tests for strip_ansi() in scripts/audit-cli-help.sh.

Regression coverage for the GitHub Actions CI failure where typer/rich emits
ANSI SGR codes in --help output under GITHUB_ACTIONS=true, splitting option
text (e.g. "--json" renders as "-" + ESC + "-json" + ESC) so literal greps
found nothing. The tests execute the real helper extracted from the script,
not a copy, so they cannot drift from the implementation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_AUDIT_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit-cli-help.sh"
_ESC = "\x1b"


def _strip_ansi_impl() -> str:
    """Extract the strip_ansi() definition verbatim from the audit script."""
    lines = _AUDIT_SCRIPT.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("strip_ansi()")),
        None,
    )
    if start is None:
        raise AssertionError(f"strip_ansi() not found in {_AUDIT_SCRIPT}")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i] == "}"),
        None,
    )
    if end is None:
        raise AssertionError(f"unterminated strip_ansi() in {_AUDIT_SCRIPT}")
    return "\n".join(lines[start : end + 1])


def _run_strip_ansi(text: str) -> str:
    """Pipe ``text`` through the real strip_ansi() in a fresh bash."""
    wrapper = f"set -euo pipefail\n{_strip_ansi_impl()}\ncat | strip_ansi\n"
    proc = subprocess.run(
        ["bash", "-c", wrapper],
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def test_strip_ansi_reassembles_esc_split_flag() -> None:
    """The exact split shape from the CI failure reassembles to --json."""
    # rich emitted: ESC[1;36m-  ESC[0m  ESC[1;36m-json  ESC[0m
    text = f"{_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-json{_ESC}[0m"
    assert _run_strip_ansi(text) == "--json"


def test_strip_ansi_reassembles_hyphenated_flag() -> None:
    """A hyphenated flag split mid-word reassembles to --dry-run."""
    # rich splits "--dry-run" into three styled segments: "-" + "-dry" + "-run".
    text = f"{_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-dry{_ESC}[0m{_ESC}[1;36m-run{_ESC}[0m"
    assert _run_strip_ansi(text) == "--dry-run"


def test_strip_ansi_plain_text_unchanged() -> None:
    """strip_ansi is a no-op on help text without ANSI codes."""
    text = "  ok  flag --uv in init\n"
    assert _run_strip_ansi(text) == text


def test_strip_ansi_option_row_keeps_flag_and_description() -> None:
    """A rich-rendered option row keeps both the flag and its description."""
    row = (
        f"{_ESC}[2m│{_ESC}[0m "
        f"{_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-json{_ESC}[0m"
        f"                          Machine-readable output."
        f"                     {_ESC}[2m│{_ESC}[0m"
    )
    stripped = _run_strip_ansi(row)
    assert "--json" in stripped
    assert "Machine-readable output." in stripped


def test_strip_ansi_ci_help_block_contains_all_global_flags() -> None:
    """A block shaped like GITHUB_ACTIONS=true main help yields the flags."""
    block = (
        f"{_ESC}[1m Usage: astroai [OPTIONS] COMMAND [ARGS]... {_ESC}[0m\n"
        f"{_ESC}[2m│{_ESC}[0m {_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-json{_ESC}[0m"
        f"    Machine-readable output.\n"
        f"{_ESC}[2m│{_ESC}[0m {_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-yes{_ESC}[0m"
        f"      Non-interactive; skip confirmations.\n"
        f"{_ESC}[2m│{_ESC}[0m {_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-dry{_ESC}[0m"
        f"{_ESC}[1;36m-run{_ESC}[0m  Show actions without executing.\n"
        f"{_ESC}[2m│{_ESC}[0m {_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-quiet{_ESC}[0m"
        f"    Minimal output.\n"
        f"{_ESC}[2m│{_ESC}[0m {_ESC}[1;36m-{_ESC}[0m{_ESC}[1;36m-version{_ESC}[0m"
        f"  Show version.\n"
    )
    stripped = _run_strip_ansi(block)
    for flag in ("--json", "--yes", "--dry-run", "--quiet", "--version"):
        assert flag in stripped
