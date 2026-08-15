from __future__ import annotations

import threading
import time

from astroai_lab.utils.timing import PhaseTimer, call_with_timeout


def test_call_with_timeout_returns_value() -> None:
    assert call_with_timeout(lambda: 7, 1.0, default=0) == 7


def test_call_with_timeout_expires() -> None:
    gate = threading.Event()

    def _block() -> str:
        gate.wait(timeout=5)
        return "late"

    assert call_with_timeout(_block, 0.05, default="skip") == "skip"
    gate.set()


def test_phase_timer_emits_names() -> None:
    seen: list[str] = []

    def _cb(name: str, dt: float, total: float) -> None:
        seen.append(name)
        assert dt >= 0
        assert total >= dt

    timer = PhaseTimer(_cb)
    with timer.phase("one"):
        time.sleep(0.01)
    with timer.phase("two"):
        pass
    assert seen == ["one", "two"]
