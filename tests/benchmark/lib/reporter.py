"""Write and aggregate benchmark result files.

Output files per run (all plain text, gitignored):
  run.json      – run metadata (written at start, finished_at updated at end)
  events.jsonl  – one JSON object per line, appended as events happen
  summary.json  – aggregated metrics, generated from events.jsonl at the end
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Reporter:
    """Thread-safe writer for benchmark result files."""

    def __init__(self, results_dir: Path, run_id: str) -> None:
        self.run_dir = results_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self.run_dir / "events.jsonl"
        self._run_path = self.run_dir / "run.json"
        self._summary_path = self.run_dir / "summary.json"
        self._lock = threading.Lock()

    # ── Run metadata ───────────────────────────────────────────────────────────

    def write_run_start(self, meta: dict[str, Any]) -> None:
        """Write run.json with started_at; call once at the beginning."""
        meta = {**meta, "started_at": _now_iso(), "finished_at": None}
        self._run_path.write_text(json.dumps(meta, indent=2, default=str) + "\n")

    def write_run_finish(self) -> None:
        """Update finished_at in run.json."""
        data = json.loads(self._run_path.read_text())
        data["finished_at"] = _now_iso()
        self._run_path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    # ── Event streaming ────────────────────────────────────────────────────────

    def emit(self, event: str, **kwargs: Any) -> None:
        """Append one event line to events.jsonl (thread-safe)."""
        record = {"ts": _now_iso(), "event": event, **kwargs}
        line = json.dumps(record, default=str) + "\n"
        with self._lock:
            with self._events_path.open("a") as f:
                f.write(line)

    # ── Summary generation ─────────────────────────────────────────────────────

    def write_summary(self, run_id: str, total_duration_sec: float) -> dict[str, Any]:
        """Read events.jsonl, aggregate metrics, write summary.json, return it."""
        events = self._load_events()
        summary = _aggregate(run_id, total_duration_sec, events)
        self._summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
        return summary

    def _load_events(self) -> list[dict[str, Any]]:
        if not self._events_path.exists():
            return []
        lines = []
        for line in self._events_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return lines

    @property
    def run_dir_path(self) -> Path:
        return self.run_dir


# ── Aggregation logic ──────────────────────────────────────────────────────────


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0, "p95": 0, "p99": 0, "max": 0}
    s = sorted(values)
    n = len(s)

    def pct(p: float) -> float:
        idx = (p / 100) * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 1)

    return {"p50": pct(50), "p95": pct(95), "p99": pct(99), "max": round(s[-1], 1)}


def _empty_bucket() -> dict[str, Any]:
    return {
        "submitted": 0,
        "created_ok": 0,
        "created_err": 0,
        "ready": 0,
        "failed_status": 0,
        "poll_timeout": 0,
        "deleted_ok": 0,
        "deleted_err": 0,
        "create_success_rate": 0.0,
        "ready_rate_of_created": 0.0,
        "ready_rate_of_submitted": 0.0,
        "create_errors": {},
        "create_latency_ms": {},
        "ready_latency_ms": {},
    }


def _finalize_bucket(b: dict[str, Any], create_latencies: list[float], ready_latencies: list[float]) -> None:
    submitted = b["submitted"]
    created_ok = b["created_ok"]
    ready = b["ready"]
    b["create_success_rate"] = round(created_ok / submitted, 4) if submitted else 0.0
    b["ready_rate_of_created"] = round(ready / created_ok, 4) if created_ok else 0.0
    b["ready_rate_of_submitted"] = round(ready / submitted, 4) if submitted else 0.0
    b["create_latency_ms"] = _percentiles(create_latencies)
    b["ready_latency_ms"] = _percentiles(ready_latencies)


def _aggregate(run_id: str, total_duration_sec: float, events: list[dict[str, Any]]) -> dict[str, Any]:
    overall = _empty_bucket()
    by_template: dict[str, dict] = {}
    by_persist: dict[str, dict] = {}

    # Per-sandbox create latency tracking
    create_latencies_all: list[float] = []
    ready_latencies_all: list[float] = []
    create_latencies_by_tmpl: dict[str, list[float]] = {}
    ready_latencies_by_tmpl: dict[str, list[float]] = {}
    create_latencies_by_persist: dict[str, list[float]] = {}
    ready_latencies_by_persist: dict[str, list[float]] = {}

    def bucket_for(tmpl: str, persist: bool | None) -> tuple[dict, dict, str]:
        if tmpl not in by_template:
            by_template[tmpl] = _empty_bucket()
            create_latencies_by_tmpl[tmpl] = []
            ready_latencies_by_tmpl[tmpl] = []
        p_key = str(persist).lower() if persist is not None else "unknown"
        if p_key not in by_persist:
            by_persist[p_key] = _empty_bucket()
            create_latencies_by_persist[p_key] = []
            ready_latencies_by_persist[p_key] = []
        return by_template[tmpl], by_persist[p_key], p_key

    for ev in events:
        event = ev.get("event", "")
        tmpl = ev.get("template", "unknown")
        persist = ev.get("persist")
        tmpl_b, persist_b, p_key = bucket_for(tmpl, persist)

        if event == "create_submitted":
            for b in (overall, tmpl_b, persist_b):
                b["submitted"] += 1

        elif event == "create_ok":
            latency = ev.get("latency_ms", 0)
            for b in (overall, tmpl_b, persist_b):
                b["created_ok"] += 1
            create_latencies_all.append(latency)
            create_latencies_by_tmpl[tmpl].append(latency)
            create_latencies_by_persist[p_key].append(latency)

        elif event == "create_err":
            status = str(ev.get("http_status", "unknown"))
            for b in (overall, tmpl_b, persist_b):
                b["created_err"] += 1
                b["create_errors"][status] = b["create_errors"].get(status, 0) + 1

        elif event == "ready":
            ready_latency = ev.get("ready_latency_ms", 0)
            for b in (overall, tmpl_b, persist_b):
                b["ready"] += 1
            ready_latencies_all.append(ready_latency)
            ready_latencies_by_tmpl[tmpl].append(ready_latency)
            ready_latencies_by_persist[p_key].append(ready_latency)

        elif event == "failed_status":
            for b in (overall, tmpl_b, persist_b):
                b["failed_status"] += 1

        elif event == "poll_timeout":
            for b in (overall, tmpl_b, persist_b):
                b["poll_timeout"] += 1

        elif event == "delete_ok":
            for b in (overall, tmpl_b, persist_b):
                b["deleted_ok"] += 1

        elif event == "delete_err":
            for b in (overall, tmpl_b, persist_b):
                b["deleted_err"] += 1

    _finalize_bucket(overall, create_latencies_all, ready_latencies_all)
    for tmpl in by_template:
        _finalize_bucket(by_template[tmpl], create_latencies_by_tmpl[tmpl], ready_latencies_by_tmpl[tmpl])
    for p_key in by_persist:
        _finalize_bucket(
            by_persist[p_key],
            create_latencies_by_persist[p_key],
            ready_latencies_by_persist[p_key],
        )

    return {
        "run_id": run_id,
        "total_duration_sec": round(total_duration_sec, 2),
        "overall": overall,
        "by_template": by_template,
        "by_persist": by_persist,
    }


def print_summary(summary: dict[str, Any]) -> None:
    """Print a human-readable summary to stdout."""
    o = summary["overall"]
    print()
    print("=" * 60)
    print(f"  Benchmark Run: {summary['run_id']}")
    print(f"  Duration: {summary['total_duration_sec']}s")
    print("=" * 60)
    print(f"  Submitted:        {o['submitted']}")
    print(f"  Created OK:       {o['created_ok']}  (success rate: {o['create_success_rate']:.1%})")
    print(f"  Created ERR:      {o['created_err']}  {o['create_errors']}")
    print(f"  Ready:            {o['ready']}  (of created: {o['ready_rate_of_created']:.1%})")
    print(f"  Failed status:    {o['failed_status']}")
    print(f"  Poll timeout:     {o['poll_timeout']}")
    print(f"  Deleted OK:       {o['deleted_ok']}")
    print()
    if o["create_latency_ms"]:
        cl = o["create_latency_ms"]
        print(f"  Create latency:   p50={cl['p50']}ms  p95={cl['p95']}ms  p99={cl['p99']}ms  max={cl['max']}ms")
    if o["ready_latency_ms"]:
        rl = o["ready_latency_ms"]
        print(f"  Ready latency:    p50={rl['p50']}ms  p95={rl['p95']}ms  p99={rl['p99']}ms  max={rl['max']}ms")
    print("=" * 60)
    if len(summary["by_template"]) > 1:
        print("  By template:")
        for tmpl, b in summary["by_template"].items():
            print(
                f"    {tmpl}: submitted={b['submitted']} ok={b['created_ok']} ready={b['ready']} err={b['created_err']}"
            )
    print()
