"""Bounded waits and optional phase timings for status probes."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from contextlib import contextmanager
from typing import TypeVar

T = TypeVar("T")

PhaseCallback = Callable[[str, float, float], None]


class PhaseTimer:
    """Record named probe durations. ``callback(name, dt, total)`` is optional."""

    def __init__(self, callback: PhaseCallback | None = None) -> None:
        self.callback = callback
        self.origin = time.perf_counter()

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            if self.callback is not None:
                now = time.perf_counter()
                self.callback(name, now - t0, now - self.origin)


def call_with_timeout(
    fn: Callable[[], T],
    timeout_sec: float,
    default: T,
) -> T:
    """Run ``fn`` in a worker thread; return ``default`` if it exceeds ``timeout_sec``.

    The worker is not cancelled. A stuck CADC client can keep a thread busy after
    status has already moved on. That is still better than blocking the CLI.
    """
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lab-timeout")
    fut = pool.submit(fn)
    try:
        return fut.result(timeout=timeout_sec)
    except FuturesTimeout:
        return default
    finally:
        # Do not join the worker. A hung CADC client must not block status.
        pool.shutdown(wait=False, cancel_futures=True)
