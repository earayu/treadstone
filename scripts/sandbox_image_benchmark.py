"""Opt-in Docker image experiment for disposable GitHub-hosted runners.

This measures image pull, container startup/restart and memory, not Kubernetes
warm-pool allocation. It never builds images or contacts the production API.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


def command(*args: str, timeout: int = 300) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()


def validate_image(image: str) -> None:
    if not re.fullmatch(r"ghcr\.io/[\w./-]+(?::v\d+\.\d+\.\d+|@sha256:[a-f0-9]{64})", image):
        raise ValueError("Use a versioned GHCR image or a sha256 digest, not latest or a local image")


def percentiles(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "p50": None, "p95": None}
    values = sorted(values)

    def percentile(fraction: float) -> float:
        index = (len(values) - 1) * fraction
        lo = int(index)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (index - lo), 3)

    return {"count": len(values), "p50": percentile(0.5), "p95": percentile(0.95)}


def memory_bytes(value: str) -> int:
    match = re.fullmatch(r"([\d.]+)\s*(B|kB|MB|GB|KiB|MiB|GiB)", value.split("/")[0].strip())
    if not match:
        raise ValueError(f"Unexpected Docker memory value: {value}")
    units = {"B": 1, "kB": 1000, "MB": 1000**2, "GB": 1000**3, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}
    return int(float(match[1]) * units[match[2]])


def aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    failures = sum(sample["error"] is not None for sample in samples)
    result: dict[str, Any] = {
        "attempts": len(samples),
        "failures": failures,
        "failure_rate": failures / len(samples) if samples else None,
    }
    for key in ("ready_seconds", "restart_seconds", "idle_memory_bytes", "active_memory_bytes"):
        result[key] = percentiles(
            [sample[key] for sample in samples if sample["error"] is None and sample.get(key) is not None]
        )
    return result


def request(base: str, path: str, *, method: str = "GET") -> Any:
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=3) as response:
        body = response.read()
        return json.loads(body) if body else None


def wait_ready(base: str, *, timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request(base, "/v1/sandbox")
            if request(base, "/cdp/json/version").get("Browser"):
                return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise TimeoutError("Runtime API and browser CDP did not become ready")


def memory_sample(name: str) -> float:
    values = [
        memory_bytes(command("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name)) for _ in range(3)
    ]
    return sum(values) / len(values)


def container_base(name: str) -> str:
    inspect = json.loads(command("docker", "inspect", name))[0]
    port = inspect["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"]
    return f"http://127.0.0.1:{port}"


def sample(image_id: str, output: Path, index: int, *, measure_memory: bool = True) -> dict[str, Any]:
    name = f"sandbox-bench-{uuid.uuid4().hex[:12]}"
    result: dict[str, Any] = {"index": index, "error": None, "ready_seconds": None}
    try:
        started = time.monotonic()
        command(
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--cpus=1",
            "--memory=2g",
            "--shm-size=512m",
            "--security-opt=no-new-privileges",
            "-p",
            "127.0.0.1::8080",
            image_id,
        )
        base = container_base(name)
        wait_ready(base)
        result["ready_seconds"] = time.monotonic() - started
        if measure_memory:
            time.sleep(3)
            result["idle_memory_bytes"] = memory_sample(name)
            html = (
                "<title>benchmark-active</title><canvas id=c width=1280 height=720></canvas>"
                "<script>let x=c.getContext('2d');function draw(t){"
                "x.fillStyle='white';x.fillRect(0,0,1280,720);"
                "for(let i=0;i<200;i++){x.fillStyle=`hsl(${i},60%,50%)`;"
                "x.fillRect((i*7+t/20)%1280,i*3%720,30,30);}requestAnimationFrame(draw);}"
                "requestAnimationFrame(draw);</script>"
            )
            # The legacy /json route forwards PUT directly; GEM's /cdp adapter
            # intentionally exposes only a subset of HTTP discovery methods.
            request(base, "/json/new?" + urllib.parse.quote("data:text/html," + html, safe=""), method="PUT")
            deadline = time.monotonic() + 20
            while not any(t.get("title") == "benchmark-active" for t in request(base, "/cdp/json/list")):
                if time.monotonic() > deadline:
                    raise TimeoutError("Browser did not load the deterministic canvas workload")
                time.sleep(0.25)
            time.sleep(3)
            result["active_memory_bytes"] = memory_sample(name)
            started = time.monotonic()
            command("docker", "restart", "--time", "30", name)
            base = container_base(name)
            wait_ready(base)
            result["restart_seconds"] = time.monotonic() - started
    except Exception as exc:
        result["error"] = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            result["error"] += f"\n{exc.stderr}"
        logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True, timeout=30)
        (output / f"failure-{index}.log").write_text(logs.stdout + logs.stderr)
        diagnostics = subprocess.run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-c",
                'nginx -t -c /opt/gem/nginx.conf; tail -n 80 "$LOG_DIR"/*.log',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        (output / f"diagnostics-{index}.log").write_text(diagnostics.stdout + diagnostics.stderr)
    finally:
        subprocess.run(["docker", "rm", "-fv", name], capture_output=True, timeout=60)
    return result


def resolve_manifest(image: str) -> tuple[str, dict[str, Any]]:
    validate_image(image)
    manifest = json.loads(command("docker", "buildx", "imagetools", "inspect", "--raw", image))
    if "manifests" in manifest:
        target = next(
            item
            for item in manifest["manifests"]
            if item.get("platform", {}).get("os") == "linux" and item["platform"].get("architecture") == "amd64"
        )
        repo = image.split("@")[0].split(":")[0]
        image = f"{repo}@{target['digest']}"
        manifest = json.loads(command("docker", "buildx", "imagetools", "inspect", "--raw", image))
    return image, manifest


def run(image: str, output: Path, samples: int, concurrency: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "requested_image": image,
        "runner": {"os": platform.platform(), "cpu_count": os.cpu_count(), "architecture": platform.machine()},
        "limits": {"cpus": 1, "memory_bytes": 2 * 1024**3, "shm_bytes": 512 * 1024**2},
        "concurrency": concurrency,
        "notes": [
            "Image pull is a single sample; shared registry/network caches are uncontrolled.",
            "Sequential starts use a cached image and a fresh home; restart is not warm-pool allocation.",
            "Memory is Docker cgroup working-set usage, not process RSS; Chromium runs even when idle.",
            "Small samples on shared runners are directional, not a production SLO or capacity claim.",
        ],
    }
    try:
        resolved, manifest = resolve_manifest(image)
        result["resolved_image"] = resolved
        result["compressed_bytes"] = sum(layer["size"] for layer in manifest["layers"]) + manifest["config"]["size"]
        cached = subprocess.run(["docker", "image", "inspect", resolved], capture_output=True).returncode == 0
        result["already_cached"] = cached
        started = time.monotonic()
        command("docker", "pull", "--platform", "linux/amd64", resolved, timeout=1200)
        result["pull_seconds"] = time.monotonic() - started
        inspect = json.loads(command("docker", "image", "inspect", resolved))[0]
        result["image_id"] = inspect["Id"]
        result["repo_digests"] = inspect["RepoDigests"]
        result["uncompressed_bytes"] = inspect["Size"]
        result["requested_samples"] = samples
        result["sequential_samples"] = []
        result["concurrent_samples"] = []
        for i in range(samples):
            trial = sample(inspect["Id"], output, i)
            result["sequential_samples"].append(trial)
            (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(f"Sequential sample {i + 1}/{samples}: {trial}", flush=True)
            if trial["ready_seconds"] is None:
                result["aborted_reason"] = "Startup failed; remaining trials skipped, not counted as successes."
                break
        if "aborted_reason" not in result:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                result["concurrent_samples"] = list(
                    executor.map(
                        lambda i: sample(inspect["Id"], output, i + samples, measure_memory=False),
                        range(samples),
                    )
                )
        result["sequential"] = aggregate(result["sequential_samples"])
        result["concurrent"] = aggregate(result["concurrent_samples"])
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def report(paths: list[Path]) -> str:
    lines = [
        "# Sandbox Image Experiment",
        "",
        "| Image | Compressed MiB | Pulled in s | Start P50/P95 s | Restart P50/P95 s "
        "| Idle/active MiB (P50) | Sequential/concurrent failures |",
        "| --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for path in paths:
        item = json.loads(path.read_text())
        if "error" in item:
            lines.append(f"| {item['requested_image']} | ERROR: {item['error']} | | | | | |")
            continue
        seq, con = item["sequential"], item["concurrent"]

        def pair(metric: str) -> str:
            return f"{seq[metric]['p50']}/{seq[metric]['p95']}"

        def mib(metric: str) -> str:
            value = seq[metric]["p50"]
            return f"{value / 1024**2:.1f}" if value is not None else "n/a"

        lines.append(
            f"| {item['requested_image']} | {item['compressed_bytes'] / 1024**2:.1f} "
            f"| {item['pull_seconds']:.1f} | {pair('ready_seconds')} | {pair('restart_seconds')} "
            f"| {mib('idle_memory_bytes')}/{mib('active_memory_bytes')} "
            f"| {seq['failures']}/{seq['attempts']}; {con['failures']}/{con['attempts']} |"
        )
    lines.extend(
        [
            "",
            "Each image uses an independent GitHub-hosted runner, with 1 CPU / 2 GiB per container.",
            "Pull is one sample; startup excludes pull. Restarts are NOT Kubernetes warm-pool allocations.",
            "Memory is the cgroup working set, not RSS. Small samples and shared runners limit conclusions.",
            "See result.json for exact digests, raw samples, concurrent latency and environment metadata.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image")
    parser.add_argument("--output", type=Path, default=Path("reports/sandbox-benchmark"))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--report", type=Path, nargs="+")
    args = parser.parse_args()
    if args.report:
        print(report(args.report), end="")
        return
    if not args.image or not 1 <= args.samples <= 20 or not 1 <= args.concurrency <= 2:
        parser.error("--image is required; samples must be 1..20 and concurrency 1..2")
    result = run(args.image, args.output, args.samples, args.concurrency)
    print(report([args.output / "result.json"]), end="")
    if result["sequential"]["failures"] or result["concurrent"]["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
