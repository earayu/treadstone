#!/usr/bin/env python3
"""Treadstone Benchmark — initialization script.

Run once before the first benchmark to ensure:
  1. The treadstone binary is installed and accessible.
  2. The current user is authenticated with the target server.
  3. Available sandbox templates are visible for pre-flight review.

Usage:
  python tests/benchmark/setup.py
  python tests/benchmark/setup.py --version 0.8.8
  python tests/benchmark/setup.py --config path/to/benchmark.config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow importing from lib/ without installing the package
sys.path.insert(0, str(Path(__file__).parent))

from lib import binary as binary_lib
from lib.executor import _run_cli, check_auth

_DEFAULT_CONFIG = Path(__file__).parent / "benchmark.config.yaml"


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        # Minimal YAML parsing using stdlib (no PyYAML dependency)
        import re

        config: dict = {}
        for line in config_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(\w+)\s*:\s*"?([^"#]*)"?\s*(?:#.*)?$', line)
            if m:
                config[m.group(1)] = m.group(2).strip()
        return config
    except Exception as e:
        print(f"Warning: Could not parse {config_path}: {e}", file=sys.stderr)
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Treadstone benchmark setup.")
    parser.add_argument("--version", default=None, help="treadstone binary version (default: from config or 'latest')")
    parser.add_argument("--binary", default=None, help="path to treadstone binary (skip install)")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="path to benchmark.config.yaml")
    args = parser.parse_args()

    config = _load_config(Path(args.config))

    version = args.version or config.get("binary_version", "latest")
    base_url = config.get("base_url") or None  # None → falls back to treadstone's own config

    print("=" * 60)
    print("  Treadstone Benchmark Setup")
    print("=" * 60)
    if base_url:
        print(f"  Target base_url: {base_url}")
    print(f"  Binary version:  {version}")
    print()

    # 1. Resolve binary
    bin_path = binary_lib.resolve(version=version, binary_override=args.binary)

    # 2. Check auth — fail fast, no auto-fix
    check_auth(bin_path, base_url)

    # 3. List templates for manual review
    print()
    print("Available sandbox templates:")
    result = _run_cli(bin_path, ["templates", "list"], base_url)
    if result["ok"] and isinstance(result.get("data"), dict):
        items = result["data"].get("items", [])
        for tmpl in items:
            name = tmpl.get("name", "?")
            cpu = tmpl.get("cpu", {})
            mem = tmpl.get("memory", {})
            print(f"  {name}  cpu={cpu.get('requests', '?')}  memory={mem.get('requests', '?')}")
    else:
        print("  (could not fetch templates — check connection)")

    print()
    print("Setup complete. Run benchmarks with:")
    print("  python tests/benchmark/runner.py tests/benchmark/scenarios/stateless_burst.yaml")
    print()


if __name__ == "__main__":
    main()
