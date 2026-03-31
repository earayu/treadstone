"""List sandboxes (control plane) — Sandbox Lifecycle “List & Inspect”.

Public docs: ``web/public/docs/sandbox-lifecycle.md``.

Usage:
  pip install treadstone-sdk
  python examples/control_plane/02_list_sandboxes.py --api-key <key> [--status ready]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXAMPLES_ROOT))

from _shared import get_control_client, parse_base_args, print_result, print_section, print_step  # noqa: E402


def main() -> int:
    base_args, rest = parse_base_args("List all sandboxes and display them grouped by status.")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--status",
        default=None,
        help="Filter by status (e.g. ready, stopped, creating, error).",
    )
    extra = parser.parse_args(rest)

    try:
        from treadstone_sdk.api.sandboxes import sandboxes_list_sandboxes
        from treadstone_sdk.models.sandbox_list_response import SandboxListResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    print_section("List Sandboxes")

    print_step("Step 1: Connect to the control plane")
    client = get_control_client(base_args.base_url, base_args.api_key)
    print(f"  Connected to {base_args.base_url}")

    print_step("Step 2: Fetch all sandboxes")
    response = sandboxes_list_sandboxes.sync(client=client)
    if not isinstance(response, SandboxListResponse):
        print("ERROR: Failed to list sandboxes.", file=sys.stderr)
        return 1

    sandboxes = response.items or []
    print(f"  Total sandboxes found: {len(sandboxes)}")

    if extra.status:
        sandboxes = [s for s in sandboxes if getattr(s, "status", None) == extra.status]
        print(f"  After filtering by status={extra.status!r}: {len(sandboxes)} sandbox(es)")

    if not sandboxes:
        print("\n  No sandboxes found.")
        return 0

    print_step("Step 3: Sandboxes grouped by status")
    by_status: dict[str, list] = defaultdict(list)
    for sb in sandboxes:
        status = getattr(sb, "status", "unknown")
        by_status[status].append(sb)

    status_order = ["ready", "creating", "stopped", "error", "deleting", "deleted", "unknown"]
    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        print(f"\n  [{status.upper()}]  ({len(group)} sandbox{'es' if len(group) != 1 else ''})")
        for sb in group:
            sb_id = getattr(sb, "id", "?")
            sb_name = getattr(sb, "name", "?")
            sb_template = getattr(sb, "template", "?")
            proxy = getattr(getattr(sb, "urls", None), "proxy", None)
            print(f"    • {sb_name}  (id: {sb_id}, template: {sb_template})")
            if proxy:
                print(f"      data-plane proxy: {proxy}")

    print_step("Step 4: Full sandbox list (JSON)")
    print_result("All sandboxes", sandboxes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
