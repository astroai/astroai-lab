"""Tests for the deterministic benchmark payload helper."""

import pytest


def benchmark_payload(size: int = 1_048_576) -> bytes:
    if size < 1:
        raise ValueError("size must be positive")
    return (b"astroai-workload\0" * ((size // 16) + 1))[:size]


def test_benchmark_payload_is_deterministic_and_sized() -> None:
    assert benchmark_payload(32) == benchmark_payload(32)
    assert len(benchmark_payload(32)) == 32


def test_benchmark_payload_rejects_non_positive_sizes() -> None:
    with pytest.raises(ValueError):
        benchmark_payload(0)
