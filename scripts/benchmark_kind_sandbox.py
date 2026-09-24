"""Small, manual cold/warm-pool experiment on a disposable CI Kind cluster."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/benchmark"))
from lib.executor import CreateTask, run_cleanup_phase, run_create_phase, run_poll_phase  # noqa: E402
from lib.reporter import Reporter  # noqa: E402
from sandbox_image_benchmark import percentiles  # noqa: E402

BASE = "http://api.localhost"
NAMESPACE = "treadstone-local"
POOL = "aio-sandbox-tiny-pool"


def kubectl(*args: str) -> str:
    return subprocess.run(
        ["kubectl", "--context", "kind-treadstone", "-n", NAMESPACE, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


def pool_sandboxes() -> list[dict[str, Any]]:
    return [
        item
        for item in json.loads(kubectl("get", "sandboxes", "-o", "json"))["items"]
        if any(
            ref["kind"] == "SandboxWarmPool" and ref["name"] == POOL
            for ref in item["metadata"].get("ownerReferences", [])
        )
    ]


def resize(replicas: int) -> None:
    kubectl("patch", "sandboxwarmpool", POOL, "--type=merge", "-p", json.dumps({"spec": {"replicas": replicas}}))


def adopted_sandboxes(claims: list[dict[str, Any]], sandbox_ids: list[str]) -> set[str]:
    return {
        claim.get("status", {}).get("sandbox", {}).get("name")
        for claim in claims
        if claim["metadata"].get("labels", {}).get("treadstone-ai.dev/sandbox-id") in sandbox_ids
    } - {None}


def wait_pool(*, empty: bool) -> list[str]:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        sandboxes = pool_sandboxes()
        ready = [
            item["metadata"]["name"]
            for item in sandboxes
            if not item["metadata"].get("deletionTimestamp")
            and any(
                condition["type"] == "Ready" and condition["status"] == "True"
                for condition in item.get("status", {}).get("conditions", [])
            )
        ]
        if (empty and not sandboxes) or (not empty and ready):
            return ready
        time.sleep(1)
    raise TimeoutError(f"Pool did not become {'empty' if empty else 'ready'}")


def authenticate() -> str:
    email = f"image-benchmark-{uuid.uuid4().hex[:8]}@test.treadstone.dev"
    password = "Benchmark-Test1!"
    with httpx.Client(base_url=BASE, timeout=30) as user, httpx.Client(base_url=BASE, timeout=30) as admin:
        user.post("/v1/auth/register", json={"email": email, "password": password}).raise_for_status()
        admin.post(
            "/v1/auth/login",
            json={"email": "e2e-admin@test.treadstone.dev", "password": "E2eStr0ng_Pass!"},
        ).raise_for_status()
        response = admin.get("/v1/admin/verification-token-by-email", params={"email": email})
        response.raise_for_status()
        token = response.json()["token"]
        user.post("/v1/auth/login", json={"email": email, "password": password}).raise_for_status()
        user.post("/v1/auth/verification/confirm", json={"token": token}).raise_for_status()
        response = user.post("/v1/auth/api-keys", json={"name": "disposable-kind-benchmark"})
        response.raise_for_status()
        return response.json()["key"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or not 1 <= args.samples <= 10:
        parser.error("Only run on disposable GitHub-hosted Kind; samples must be 1..10")
    kubectl("get", "sandboxwarmpool", POOL)
    output = ROOT / "reports/sandbox-kind-benchmark"
    output.mkdir(parents=True, exist_ok=True)
    os.environ["TREADSTONE_API_KEY"] = authenticate()
    print(f"::add-mask::{os.environ['TREADSTONE_API_KEY']}")
    results: dict[str, Any] = {
        "image": os.environ.get("SANDBOX_IMAGE") or "PR-built image",
        "samples": [],
        "notes": [
            "Cold = empty pool replenished immediately before create; image is already cached on Kind nodes.",
            "Warm = Ready pool Sandbox observed before create; adoption must match that observed set.",
            "End-to-end timing includes pool resize (cold only), CLI create and readiness polling at 1s intervals.",
            "Three samples per mode are a smoke baseline, not production capacity or reliable tail estimates.",
        ],
    }
    pools = json.loads(kubectl("get", "sandboxwarmpools", "-o", "json"))["items"]
    try:
        # Remove idle pools for larger tiers so the small runner has comparable headroom.
        for pool in pools:
            kubectl(
                "patch",
                "sandboxwarmpool",
                pool["metadata"]["name"],
                "--type=merge",
                "-p",
                '{"spec":{"replicas":0}}',
            )
        for mode in ("cold", "warm"):
            for index in range(args.samples):
                resize(0)
                wait_pool(empty=True)
                observed: list[str] = []
                if mode == "warm":
                    resize(1)
                    observed = wait_pool(empty=False)
                run_id = f"{mode}-{index}-{uuid.uuid4().hex[:8]}"
                label = f"loadtest:run-{run_id}"
                reporter = Reporter(output, run_id)
                reporter.write_run_start({"mode": mode, "observed_ready_pool": observed, "image": results["image"]})
                task = CreateTask(0, "aio-sandbox-tiny", False, None, 60, -1, label)
                record: dict[str, Any] = {"mode": mode, "run_id": run_id, "error": None}
                started = time.monotonic()
                try:
                    if mode == "cold":
                        resize(1)
                    ids = run_create_phase([task], args.binary, BASE, 1, reporter)
                    run_poll_phase(ids, args.binary, BASE, 300, 1, 1, reporter)
                    record["ready_seconds"] = time.monotonic() - started
                    claims = json.loads(kubectl("get", "sandboxclaims", "-o", "json"))["items"]
                    adopted = adopted_sandboxes(claims, ids)
                    record["adopted_sandboxes"] = sorted(adopted)
                    record["observed_ready_pool"] = observed
                    record["confirmed_warm_adoption"] = bool(set(observed) & adopted)
                    summary = reporter.write_summary(run_id, time.monotonic() - started)
                    if summary["overall"]["ready"] != 1:
                        raise AssertionError(f"Sample did not become ready: {summary['overall']}")
                    if mode == "warm" and not record["confirmed_warm_adoption"]:
                        raise AssertionError("Claim did not adopt the observed pre-warmed Sandbox")
                except Exception as exc:
                    record["error"] = str(exc)
                finally:
                    run_cleanup_phase(label, args.binary, BASE, reporter)
                    reporter.write_run_finish()
                    summary = reporter.write_summary(run_id, time.monotonic() - started)
                    if summary["overall"]["deleted_ok"] != summary["overall"]["created_ok"]:
                        record["error"] = record["error"] or "Cleanup did not delete every created sandbox"
                    results["samples"].append(record)
    finally:
        for pool in pools:
            kubectl(
                "patch",
                "sandboxwarmpool",
                pool["metadata"]["name"],
                "--type=merge",
                "-p",
                json.dumps({"spec": {"replicas": pool["spec"]["replicas"]}}),
            )
        for mode in ("cold", "warm"):
            samples = [item for item in results["samples"] if item["mode"] == mode]
            results[mode] = {
                "attempts": len(samples),
                "failures": sum(item["error"] is not None for item in samples),
                "ready_seconds": percentiles([item["ready_seconds"] for item in samples if item["error"] is None]),
            }
        (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    if any(item["error"] for item in results["samples"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
