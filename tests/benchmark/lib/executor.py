"""Concurrent sandbox create, poll, and cleanup logic.

Uses ThreadPoolExecutor (suitable for subprocess-based CLI calls).
Auth failures cause immediate sys.exit(1).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .reporter import Reporter

# ── CLI helpers ────────────────────────────────────────────────────────────────


def _run_cli(binary: Path, args: list[str], base_url: str | None = None) -> dict[str, Any]:
    """Run treadstone CLI with --json flag, return parsed JSON output.

    Returns a dict with:
      "ok": bool
      "data": dict | list  (parsed JSON on success)
      "exit_code": int
      "raw": str           (stdout)
      "error": str         (stderr on failure)
      "http_status": int | None  (extracted from error envelope if present)
    """
    cmd = [str(binary), "--json"]
    if base_url:
        cmd += ["--base-url", base_url]
    cmd += args

    result = subprocess.run(cmd, capture_output=True, text=True)
    raw = result.stdout.strip()
    ok = result.returncode == 0

    http_status: int | None = None
    data: Any = None

    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "error" in data:
                err_obj = data["error"]
                http_status = err_obj.get("status") if isinstance(err_obj, dict) else None
                ok = False
        except json.JSONDecodeError:
            pass

    return {
        "ok": ok,
        "data": data,
        "exit_code": result.returncode,
        "raw": raw,
        "error": result.stderr.strip(),
        "http_status": http_status,
    }


def check_auth(binary: Path, base_url: str | None) -> None:
    """Verify treadstone auth. Exits with error message if not authenticated."""
    print("Checking authentication...")
    result = _run_cli(binary, ["auth", "whoami"], base_url)
    if not result["ok"]:
        print("Error: Not authenticated with treadstone.", file=sys.stderr)
        print("  Run: treadstone auth login", file=sys.stderr)
        print("  Or:  treadstone config set api_key <your-key>", file=sys.stderr)
        sys.exit(1)
    data = result.get("data") or {}
    email = data.get("email", "unknown")
    print(f"Authenticated as: {email}")


# ── Task types ─────────────────────────────────────────────────────────────────


class CreateTask:
    """Represents one sandbox creation task expanded from a scenario matrix entry."""

    def __init__(
        self,
        profile_idx: int,
        template: str,
        persist: bool,
        storage_size: str | None,
        auto_stop_interval: int,
        auto_delete_interval: int,
        run_label: str,
    ) -> None:
        self.profile_idx = profile_idx
        self.template = template
        self.persist = persist
        self.storage_size = storage_size
        self.auto_stop_interval = auto_stop_interval
        self.auto_delete_interval = auto_delete_interval
        self.run_label = run_label


# ── Core execution phases ──────────────────────────────────────────────────────


def run_create_phase(
    tasks: list[CreateTask],
    binary: Path,
    base_url: str | None,
    concurrency: int,
    reporter: Reporter,
) -> list[str]:
    """Submit all create tasks concurrently. Returns list of created sandbox IDs."""
    created_ids: list[str] = []
    lock = __import__("threading").Lock()

    def do_create(task: CreateTask) -> None:
        reporter.emit(
            "create_submitted",
            profile_idx=task.profile_idx,
            template=task.template,
            persist=task.persist,
            storage_size=task.storage_size,
        )
        args = [
            "sandboxes",
            "create",
            "--template",
            task.template,
            "--label",
            task.run_label,
            "--auto-stop-interval",
            str(task.auto_stop_interval),
            "--auto-delete-interval",
            str(task.auto_delete_interval),
        ]
        if task.persist:
            args.append("--persist")
        if task.storage_size:
            args += ["--storage-size", task.storage_size]

        t0 = time.monotonic()
        result = _run_cli(binary, args, base_url)
        latency_ms = round((time.monotonic() - t0) * 1000)

        if result["ok"] and isinstance(result.get("data"), dict):
            sandbox_id = result["data"].get("id", "")
            reporter.emit(
                "create_ok",
                sandbox_id=sandbox_id,
                profile_idx=task.profile_idx,
                template=task.template,
                persist=task.persist,
                http_status=202,
                latency_ms=latency_ms,
            )
            with lock:
                created_ids.append(sandbox_id)
        else:
            http_status = result.get("http_status") or result.get("exit_code")
            error_msg = ""
            if isinstance(result.get("data"), dict) and "error" in result["data"]:
                err = result["data"]["error"]
                error_msg = err.get("message", "") if isinstance(err, dict) else str(err)
            else:
                error_msg = result.get("error") or result.get("raw") or "unknown error"
            reporter.emit(
                "create_err",
                profile_idx=task.profile_idx,
                template=task.template,
                persist=task.persist,
                http_status=http_status,
                latency_ms=latency_ms,
                error=error_msg[:200],
            )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(do_create, task) for task in tasks]
        done = 0
        total = len(futures)
        for future in as_completed(futures):
            future.result()  # re-raise exceptions
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  Create phase: {done}/{total} submitted", end="\r")
    print()
    print(f"  Create phase done: {len(created_ids)}/{len(tasks)} accepted by API")
    return created_ids


def run_poll_phase(
    sandbox_ids: list[str],
    binary: Path,
    base_url: str | None,
    ready_timeout_sec: int,
    poll_interval_sec: int,
    concurrency: int,
    reporter: Reporter,
) -> None:
    """Poll each sandbox until ready/failed/timeout."""

    def do_poll(sandbox_id: str) -> None:
        t0 = time.monotonic()
        polls = 0
        while True:
            elapsed = time.monotonic() - t0
            if elapsed >= ready_timeout_sec:
                reporter.emit(
                    "poll_timeout",
                    sandbox_id=sandbox_id,
                    last_status="unknown",
                    elapsed_ms=round(elapsed * 1000),
                )
                return

            result = _run_cli(binary, ["sandboxes", "get", sandbox_id], base_url)
            polls += 1
            if result["ok"] and isinstance(result.get("data"), dict):
                status = result["data"].get("status", "")
                template = result["data"].get("template", "")
                persist = result["data"].get("persist", False)

                if status == "ready":
                    elapsed_ms = round((time.monotonic() - t0) * 1000)
                    reporter.emit(
                        "ready",
                        sandbox_id=sandbox_id,
                        template=template,
                        persist=persist,
                        ready_latency_ms=elapsed_ms,
                        polls=polls,
                    )
                    return
                elif status in ("failed", "error"):
                    reporter.emit(
                        "failed_status",
                        sandbox_id=sandbox_id,
                        template=template,
                        persist=persist,
                        last_status=status,
                    )
                    return
            time.sleep(poll_interval_sec)

    print(f"  Polling {len(sandbox_ids)} sandboxes (timeout={ready_timeout_sec}s)...")
    with ThreadPoolExecutor(max_workers=min(concurrency, len(sandbox_ids) or 1)) as pool:
        futures = {pool.submit(do_poll, sid): sid for sid in sandbox_ids}
        done = 0
        total = len(futures)
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  Poll phase: {done}/{total} resolved", end="\r")
    print()
    print("  Poll phase done.")


def _parse_run_label_value(run_label: str) -> tuple[str, str] | None:
    """Parse 'loadtest:run-<run_id>' into (key, value) for matching labels dict."""
    if ":" not in run_label:
        return None
    key, _, rest = run_label.partition(":")
    rest = rest.strip()
    if not key or not rest:
        return None
    return key, rest


def run_cleanup_phase(
    run_label: str,
    binary: Path,
    base_url: str | None,
    reporter: Reporter,
    persist_filter: bool | None = False,
) -> None:
    """Delete all sandboxes created by this run (identified by run_label).

    Prefer server-side --label filter; if that fails (some deployments return 500),
    fall back to listing sandboxes and filtering by labels client-side.
    persist_filter=False: only delete non-persistent sandboxes (safe default).
    persist_filter=True: only delete persistent sandboxes.
    persist_filter=None: delete all matching the label regardless of persist.
    """
    print(f"  Fetching sandboxes with label {run_label!r} for cleanup...")
    result = _run_cli(binary, ["sandboxes", "list", "--label", run_label, "--limit", "1000"], base_url)
    items: list[dict[str, Any]] = []
    if result["ok"] and isinstance(result.get("data"), dict):
        items = result["data"].get("items", [])
    else:
        print(
            "  Note: list --label failed; falling back to full list + client-side label match.",
            file=sys.stderr,
        )
        result = _run_cli(binary, ["sandboxes", "list", "--limit", "1000"], base_url)
        if not result["ok"] or not isinstance(result.get("data"), dict):
            print("  Warning: Could not list sandboxes for cleanup. Manual cleanup may be needed.", file=sys.stderr)
            return
        all_items = result["data"].get("items", [])
        parsed = _parse_run_label_value(run_label)
        if not parsed:
            print("  Warning: Unrecognized run_label format; cannot filter client-side.", file=sys.stderr)
            return
        key, want_val = parsed
        for sb in all_items:
            labels = sb.get("labels") or {}
            if str(labels.get(key)) == want_val:
                items.append(sb)

    if not items:
        print("  No sandboxes matched this run label (already clean).")
    to_delete = []
    for sb in items:
        sb_persist = sb.get("persist", False)
        if persist_filter is None or sb_persist == persist_filter:
            to_delete.append(sb["id"])
        else:
            print(f"  Skipping sandbox {sb['id']} (persist={sb_persist}) — not in filter.")

    print(f"  Deleting {len(to_delete)} sandbox(es)...")

    def do_delete(sandbox_id: str) -> None:
        result = _run_cli(binary, ["sandboxes", "delete", sandbox_id], base_url)
        if result["ok"] or result["exit_code"] == 0:
            reporter.emit("delete_ok", sandbox_id=sandbox_id)
        else:
            error = result.get("error") or result.get("raw") or "unknown"
            reporter.emit("delete_err", sandbox_id=sandbox_id, error=error[:200])

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(do_delete, sid) for sid in to_delete]
        for f in as_completed(futures):
            f.result()

    print(f"  Cleanup done: {len(to_delete)} sandbox(es) processed.")
