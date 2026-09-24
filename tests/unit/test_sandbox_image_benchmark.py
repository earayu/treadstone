"""Pure helpers for the opt-in remote image experiment (no Docker required)."""

import importlib.util
import json
import subprocess
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


def test_failed_container_is_cleaned_up(benchmark: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fail(*args: str, **kwargs: object) -> str:
        raise subprocess.CalledProcessError(1, args, stderr="container failed to start")

    def capture(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="startup log", stderr="")

    monkeypatch.setattr(benchmark, "command", fail)
    monkeypatch.setattr(benchmark.subprocess, "run", capture)
    result = benchmark.sample("sha256:tested-image", tmp_path, 3)
    assert result["ready_seconds"] is None
    assert "container failed to start" in result["error"]
    assert calls[-1][:3] == ["docker", "rm", "-fv"]
    assert (tmp_path / "failure-3.log").read_text() == "startup log"


def test_failed_pull_still_writes_evidence(
    benchmark: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(image: str) -> tuple[str, dict]:
        raise ValueError("unavailable manifest")

    monkeypatch.setattr(benchmark, "resolve_manifest", fail)
    with pytest.raises(ValueError, match="unavailable manifest"):
        benchmark.run("ghcr.io/earayu/treadstone-sandbox:v0.3.0", tmp_path, 1, 1)
    report = json.loads((tmp_path / "result.json").read_text())
    assert report["error"] == "unavailable manifest"
    assert "not a production SLO" in " ".join(report["notes"])


def test_restart_rediscovers_random_host_port(
    benchmark: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ports = iter(("18080", "28080"))
    waited: list[str] = []

    def command(*args: str, **kwargs: object) -> str:
        if args[1] == "inspect":
            return json.dumps([{"NetworkSettings": {"Ports": {"8080/tcp": [{"HostPort": next(ports)}]}}}])
        return ""

    def request(base: str, path: str, **kwargs: object) -> list[dict[str, str]]:
        return [{"title": "benchmark-active"}]

    monkeypatch.setattr(benchmark, "command", command)
    monkeypatch.setattr(benchmark, "wait_ready", lambda base: waited.append(base))
    monkeypatch.setattr(benchmark, "request", request)
    monkeypatch.setattr(benchmark, "memory_sample", lambda name: 1024)
    monkeypatch.setattr(benchmark.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        benchmark.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "", "")
    )
    result = benchmark.sample("sha256:tested", tmp_path, 0)
    assert result["error"] is None
    assert waited == ["http://127.0.0.1:18080", "http://127.0.0.1:28080"]
