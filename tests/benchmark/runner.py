#!/usr/bin/env python3
"""Treadstone Benchmark Runner — main entry point.

Reads a scenario YAML file, expands the matrix into creation tasks, runs
create → poll → cleanup phases, and writes structured results to the
results directory.

Usage:
  python tests/benchmark/runner.py <scenario_file> [options]

Options:
  --version TEXT        treadstone binary version (default: from config or 'latest')
  --binary PATH         use this binary directly (skip install/version check)
  --base-url URL        override base_url from config/env
  --config PATH         path to benchmark.config.yaml (default: ./benchmark.config.yaml)
  --results-dir PATH    override results output directory
  --no-cleanup          skip post-run sandbox deletion (debug mode)
  --dry-run             expand matrix and print task counts without creating anything
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Allow importing lib/ without installing the package
sys.path.insert(0, str(Path(__file__).parent))

from lib import binary as binary_lib
from lib.executor import CreateTask, check_auth, run_cleanup_phase, run_create_phase, run_poll_phase
from lib.reporter import Reporter, print_summary

_DEFAULT_CONFIG = Path(__file__).parent / "benchmark.config.yaml"
_DEFAULT_RESULTS_DIR = Path(__file__).parent / "results"

# ── YAML / config loading ──────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict:
    """Minimal YAML parser for simple benchmark config/scenario files.

    Supports: string scalars, booleans, integers, block sequences (- key: val),
    and nested mappings. Does not support anchors, multi-line strings, or
    complex YAML features — sufficient for our scenario format.
    """
    try:
        import tomllib  # noqa: F401 — just a check for Python version
    except ImportError:
        pass

    text = path.read_text()
    return _parse_yaml_simple(text)


def _parse_yaml_simple(text: str) -> dict:
    """Parse a restricted subset of YAML into Python dicts/lists."""
    lines = text.splitlines()
    result: dict = {}
    _parse_block(lines, 0, 0, result)
    return result


def _coerce(value: str):
    """Convert YAML scalar strings to Python types."""
    # Strip inline comments (unless the value is quoted)
    raw = value.strip()
    if raw.startswith('"') or raw.startswith("'"):
        stripped = raw.strip('"').strip("'")
    else:
        # Remove inline comment: everything from unquoted ' #' onwards
        stripped = re.split(r"\s+#", raw)[0].strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if stripped.lower() in ("null", "~", ""):
        return None
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _parse_block(lines: list[str], start: int, base_indent: int, target: dict) -> int:
    """Parse a YAML mapping block into target dict. Returns index after the block."""
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        ind = _indent(line)
        if ind < base_indent:
            break
        # Sequence item
        if stripped.startswith("- "):
            break
        # Key: value
        m = re.match(r"^(\s*)(\w[\w\-]*)\s*:\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(2)
        val_str = m.group(3).strip()
        if val_str and not val_str.startswith("#"):
            target[key] = _coerce(val_str)
            i += 1
        else:
            # Look ahead for nested block or sequence
            i += 1
            child_lines = []
            while i < len(lines):
                nline = lines[i]
                nstripped = nline.strip()
                if not nstripped or nstripped.startswith("#"):
                    i += 1
                    continue
                nind = _indent(nline)
                if nind <= ind:
                    break
                child_lines.append(nline)
                i += 1
            if child_lines and child_lines[0].strip().startswith("- "):
                target[key] = _parse_sequence(child_lines)
            else:
                nested: dict = {}
                _parse_block(child_lines, 0, 0, nested)
                target[key] = nested
    return i


def _parse_sequence(lines: list[str]) -> list:
    """Parse a YAML sequence (list of mappings) block."""
    result = []
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current is not None:
                result.append(current)
            current = {}
            rest = stripped[2:].strip()
            if rest and not rest.startswith("#"):
                m = re.match(r"^(\w[\w\-]*)\s*:\s*(.*)", rest)
                if m:
                    current[m.group(1)] = _coerce(m.group(2))
        elif current is not None:
            m = re.match(r"^[\w\-]+\s*:\s*(.*)", stripped)
            if m:
                key_m = re.match(r"^([\w\-]+)\s*:\s*(.*)", stripped)
                if key_m:
                    current[key_m.group(1)] = _coerce(key_m.group(2))
    if current is not None:
        result.append(current)
    return result


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        return _load_yaml(config_path)
    except Exception as e:
        print(f"Warning: Could not parse {config_path}: {e}", file=sys.stderr)
        return {}


# ── Scenario loading and validation ───────────────────────────────────────────


def load_scenario(path: Path) -> dict:
    """Load and validate a scenario YAML file."""
    if not path.exists():
        print(f"Error: Scenario file not found: {path}", file=sys.stderr)
        sys.exit(1)
    scenario = _load_yaml(path)
    _validate_scenario(scenario, path)
    return scenario


def _validate_scenario(scenario: dict, path: Path) -> None:
    errors = []
    if not scenario.get("name"):
        errors.append("'name' is required")
    matrix = scenario.get("matrix")
    if not matrix or not isinstance(matrix, list):
        errors.append("'matrix' must be a non-empty list")
    else:
        for i, entry in enumerate(matrix):
            if not entry.get("template"):
                errors.append(f"matrix[{i}]: 'template' is required")
            if not isinstance(entry.get("count", 0), int) or entry.get("count", 0) <= 0:
                errors.append(f"matrix[{i}]: 'count' must be a positive integer")
            if entry.get("persist") and not entry.get("storage_size"):
                errors.append(f"matrix[{i}]: 'storage_size' is required when persist=true")
    if errors:
        print(f"Error: Invalid scenario file {path}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)


def expand_matrix(scenario: dict, run_label: str) -> list[CreateTask]:
    """Expand scenario matrix into individual CreateTask objects."""
    tasks = []
    auto_stop = scenario.get("auto_stop_interval", 60)
    auto_delete = scenario.get("auto_delete_interval", -1)
    for idx, entry in enumerate(scenario["matrix"]):
        template = entry["template"]
        count = entry["count"]
        persist = bool(entry.get("persist", False))
        storage_size = entry.get("storage_size") if persist else None
        for _ in range(count):
            tasks.append(
                CreateTask(
                    profile_idx=idx,
                    template=template,
                    persist=persist,
                    storage_size=storage_size,
                    auto_stop_interval=auto_stop,
                    auto_delete_interval=auto_delete,
                    run_label=run_label,
                )
            )
    return tasks


# ── Run ID and machine info ────────────────────────────────────────────────────


def make_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def machine_info() -> str:
    return f"{platform.machine()}-{platform.system().lower()}"


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Treadstone benchmark runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scenario", help="Path to scenario YAML file")
    parser.add_argument("--version", default=None, help="treadstone binary version (default: 'latest')")
    parser.add_argument("--binary", default=None, help="path to treadstone binary (skip install)")
    parser.add_argument("--base-url", default=None, dest="base_url", help="override Treadstone base URL")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="path to benchmark.config.yaml")
    parser.add_argument("--results-dir", default=None, dest="results_dir", help="override results directory")
    parser.add_argument("--no-cleanup", action="store_true", help="skip post-run sandbox deletion")
    parser.add_argument("--dry-run", action="store_true", help="expand matrix without creating sandboxes")
    args = parser.parse_args()

    # Load config
    config = _load_config(Path(args.config))
    version = args.version or config.get("binary_version", "latest")
    base_url = args.base_url or os.environ.get("TREADSTONE_BASE_URL") or config.get("base_url") or None
    results_dir = Path(args.results_dir or config.get("results_dir") or _DEFAULT_RESULTS_DIR)

    # Load scenario
    scenario_path = Path(args.scenario)
    scenario = load_scenario(scenario_path)

    # Expand matrix
    run_id = make_run_id()
    run_label = f"loadtest:run-{run_id}"
    tasks = expand_matrix(scenario, run_label)

    total = len(tasks)
    print()
    print("=" * 60)
    print(f"  Scenario:  {scenario['name']}")
    print(f"  Run ID:    {run_id}")
    print(f"  Label:     {run_label}")
    print(f"  Tasks:     {total} sandbox(es)")
    for entry in scenario["matrix"]:
        persist_label = f"persist={entry.get('persist', False)}"
        if entry.get("persist") and entry.get("storage_size"):
            persist_label += f" storage={entry['storage_size']}"
        print(f"             {entry['count']} × {entry['template']} ({persist_label})")
    print(f"  Concurrency: {scenario.get('concurrency', 10)}")
    print(f"  ready_timeout_sec: {scenario.get('ready_timeout_sec', 900)}")
    if base_url:
        print(f"  Base URL:  {base_url}")
    print("=" * 60)

    if args.dry_run:
        print()
        print("Dry run — no sandboxes will be created.")
        return

    # Resolve binary
    bin_path = binary_lib.resolve(version=version, binary_override=args.binary)

    # Check auth
    check_auth(bin_path, base_url)

    # Set up reporter
    reporter = Reporter(results_dir, run_id)

    # Write run metadata
    treadstone_version = binary_lib._get_version(bin_path)
    reporter.write_run_start(
        {
            "run_id": run_id,
            "scenario_file": str(scenario_path),
            "scenario": scenario,
            "treadstone_version": treadstone_version,
            "treadstone_binary": str(bin_path),
            "base_url": base_url or "(from treadstone config)",
            "machine": machine_info(),
            "run_label": run_label,
        }
    )

    t_start = time.monotonic()
    should_cleanup = not args.no_cleanup
    created_ids: list[str] = []

    try:
        # Phase 1: Create
        print()
        print(f"Phase 1/3: Creating {total} sandbox(es) with concurrency={scenario.get('concurrency', 10)}...")
        created_ids = run_create_phase(
            tasks=tasks,
            binary=bin_path,
            base_url=base_url,
            concurrency=scenario.get("concurrency", 10),
            reporter=reporter,
        )

        # Phase 2: Poll
        print()
        print(f"Phase 2/3: Polling {len(created_ids)} sandbox(es) until ready...")
        run_poll_phase(
            sandbox_ids=created_ids,
            binary=bin_path,
            base_url=base_url,
            ready_timeout_sec=scenario.get("ready_timeout_sec", 900),
            poll_interval_sec=scenario.get("poll_interval_sec", 10),
            concurrency=scenario.get("concurrency", 10),
            reporter=reporter,
        )

    except KeyboardInterrupt:
        print("\nInterrupted — proceeding to cleanup.", file=sys.stderr)
        should_cleanup = should_cleanup and scenario.get("cleanup", {}).get("on_failure", True)

    # Phase 3: Cleanup
    print()
    if should_cleanup:
        print("Phase 3/3: Cleaning up...")
        # Determine persist_filter from matrix (if all entries share same persist, use it;
        # otherwise use None to clean up everything with the run label)
        persist_values = {bool(e.get("persist", False)) for e in scenario["matrix"]}
        persist_filter: bool | None = persist_values.pop() if len(persist_values) == 1 else None
        run_cleanup_phase(
            run_label=run_label,
            binary=bin_path,
            base_url=base_url,
            reporter=reporter,
            persist_filter=persist_filter,
        )
    else:
        print("Phase 3/3: Cleanup skipped (--no-cleanup). Sandboxes remain tagged with:")
        print(f"  {run_label}")

    # Finalize
    total_duration = time.monotonic() - t_start
    reporter.write_run_finish()
    summary = reporter.write_summary(run_id, total_duration)

    print_summary(summary)
    print(f"Results written to: {reporter.run_dir_path}")


if __name__ == "__main__":
    main()
