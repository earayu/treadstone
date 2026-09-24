"""Pure helpers for the opt-in remote image experiment (no Docker required)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/sandbox_image_benchmark.py"


@pytest.fixture
def benchmark() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sandbox_image_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_percentiles_do_not_report_zero_for_missing_samples(benchmark: ModuleType) -> None:
    assert benchmark.percentiles([]) == {"count": 0, "p50": None, "p95": None}
    assert benchmark.percentiles([1, 2, 3, 4, 5]) == {"count": 5, "p50": 3, "p95": 4.8}


@pytest.mark.parametrize("text,expected", [("1.5GiB / 2GiB", 1610612736), ("250MiB", 262144000)])
def test_parse_docker_memory(benchmark: ModuleType, text: str, expected: int) -> None:
    assert benchmark.memory_bytes(text) == expected


def test_failure_samples_are_not_counted_as_success(benchmark: ModuleType) -> None:
    result = benchmark.aggregate([{"ready_seconds": 2.0, "error": None}, {"ready_seconds": None, "error": "timed out"}])
    assert result["attempts"] == 2
    assert result["failures"] == 1
    assert result["failure_rate"] == 0.5
    assert result["ready_seconds"]["count"] == 1
    assert result["ready_seconds"]["p50"] == 2.0


def test_image_ref_rejects_options_and_unqualified_images(benchmark: ModuleType) -> None:
    for ref in ("--help", "ubuntu", "ghcr.io/earayu/treadstone-sandbox:latest", "x\nx"):
        with pytest.raises(ValueError):
            benchmark.validate_image(ref)
    benchmark.validate_image("ghcr.io/earayu/treadstone-sandbox:v0.3.0")
    benchmark.validate_image("ghcr.io/earayu/treadstone-sandbox@sha256:" + "a" * 64)
