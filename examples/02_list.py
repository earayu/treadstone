"""Example 02 — List Sandboxes

This example demonstrates how to query the control plane for sandbox inventory:

  1. List all sandboxes owned by the authenticated user.
  2. Group and display them by status (ready / stopped / creating / error).
  3. Show detailed information for each sandbox.

Usage:
  pip install treadstone-sdk
  python examples/02_list.py --api-key <key> [--status ready]

Sandbox statuses:
  creating  — being provisioned (typically 30–90 s)
  ready     — running and accepting data-plane requests
  stopped   — paused; data is preserved, compute is released
  error     — failed to start or encountered a fatal error
  deleting  — being torn down
  deleted   — removed (may appear briefly before disappearing from the list)
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from _shared import get_control_client, parse_args, print_result, print_section, print_step


def main() -> int:
    # --- Parse arguments ---
    base_args = parse_args("List all sandboxes and display them grouped by status.")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--status",
        default=None,
        help="Filter by status (e.g. ready, stopped, creating, error).",
    )
    extra, _ = parser.parse_known_args()

    try:
        from treadstone_sdk.api.sandboxes import sandboxes_list_sandboxes
        from treadstone_sdk.models.sandbox_list_response import SandboxListResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    print_section("List Sandboxes")

    # --- Step 1: Connect to the control plane ---
    print_step("Step 1: Connect to the control plane")
    # control plane: manages sandbox inventory and lifecycle
    client = get_control_client(base_args.base_url, base_args.api_key)
    print(f"  Connected to {base_args.base_url}")

    # --- Step 2: Fetch the sandbox list ---
    print_step("Step 2: Fetch all sandboxes")
    # control plane: GET /v1/sandboxes
    response = sandboxes_list_sandboxes.sync(client=client)
    if not isinstance(response, SandboxListResponse):
        print("ERROR: Failed to list sandboxes.", file=sys.stderr)
        return 1

    sandboxes = response.items or []
    print(f"  Total sandboxes found: {len(sandboxes)}")

    # --- Step 3: Optionally filter by status ---
    if extra.status:
        sandboxes = [s for s in sandboxes if getattr(s, "status", None) == extra.status]
        print(f"  After filtering by status={extra.status!r}: {len(sandboxes)} sandbox(es)")

    if not sandboxes:
        print("\n  No sandboxes found.")
        return 0

    # --- Step 4: Group by status ---
    print_step("Step 4: Sandboxes grouped by status")
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
                # The proxy URL is how you reach this sandbox's data plane.
                print(f"      data-plane proxy: {proxy}")

    # --- Step 5: Full detail dump ---
    print_step("Step 5: Full sandbox list (JSON)")
    print_result("All sandboxes", sandboxes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
