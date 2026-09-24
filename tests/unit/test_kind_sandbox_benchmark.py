"""The Kind experiment must not count unrelated claims as warm-pool hits."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def benchmark(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("benchmark_kind_sandbox", ROOT / "scripts/benchmark_kind_sandbox.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_warm_adoption_only_matches_current_sample(benchmark: ModuleType) -> None:
    claims = [
        {
            "metadata": {"labels": {"treadstone-ai.dev/sandbox-id": sandbox_id}},
            "status": {"sandbox": {"name": name}},
        }
        for sandbox_id, name in (("current", "pool-new"), ("unrelated", "pool-ready-before-create"))
    ]
    assert benchmark.adopted_sandboxes(claims, ["current"]) == {"pool-new"}
    assert benchmark.adopted_sandboxes(claims, []) == set()
    assert benchmark.adopted_sandboxes([{"metadata": {}}], ["current"]) == set()


def test_kind_experiment_refuses_normal_local_execution(benchmark: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("sys.argv", ["benchmark_kind_sandbox", "--binary", "/unused"])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2
