"""Example 03 — Sandbox Lifecycle (Stop & Start)

This example demonstrates the control-plane stop/start lifecycle:

  1. Resolve a sandbox (use --sandbox-id or create a fresh one).
  2. Stop the sandbox  → wait for status "stopped".
  3. Start the sandbox → wait for status "ready".

Stopping a sandbox releases compute resources while preserving all stored data.
Starting resumes the sandbox from the same state.

Usage:
  pip install treadstone-sdk

  # Use an existing sandbox:
  python examples/03_lifecycle.py --api-key <key> --sandbox-id <id>

  # Create a temporary sandbox for this demo:
  python examples/03_lifecycle.py --api-key <key>

Sandbox status transitions relevant to this example:
  ready → (stop) → stopped → (start) → ready
"""

from __future__ import annotations

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from _shared import (
    get_control_client,
    make_sandbox_name,
    parse_args,
    print_result,
    print_section,
    print_step,
    wait_for_sandbox,
)


def main() -> int:
    args = parse_args("Stop and start a sandbox to demonstrate lifecycle management.")

    try:
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_delete_sandbox,
            sandboxes_get_sandbox,
            sandboxes_start_sandbox,
            sandboxes_stop_sandbox,
        )
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    print_section("Sandbox Lifecycle: Stop → Start")

    # --- Step 1: Connect to the control plane ---
    print_step("Step 1: Connect to the control plane")
    # control plane: all lifecycle calls go through the Treadstone API
    client = get_control_client(args.base_url, args.api_key)
    print(f"  Connected to {args.base_url}")

    created_here = False
    sandbox_id = args.sandbox_id

    # --- Step 2: Resolve sandbox ---
    print_step("Step 2: Resolve target sandbox")
    if sandbox_id:
        print(f"  Using existing sandbox: {sandbox_id}")
        # Verify it exists and is ready before we try to stop it.
        detail = sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client)
        if not isinstance(detail, SandboxDetailResponse):
            print(f"ERROR: Sandbox {sandbox_id} not found.", file=sys.stderr)
            return 1
        print(f"  Current status: {detail.status}")
        if detail.status != "ready":
            print(f"  Sandbox is {detail.status!r}, not 'ready' — waiting for ready first.")
            detail = wait_for_sandbox(
                fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
                target_status="ready",
            )
    else:
        # No sandbox provided: create a temporary one for this demo.
        print("  No --sandbox-id provided; creating a temporary sandbox.")
        name = make_sandbox_name("example-03")
        created = sandboxes_create_sandbox.sync(
            client=client,
            body=CreateSandboxRequest(template=args.template, name=name),
        )
        if not isinstance(created, SandboxResponse):
            print("ERROR: Failed to create sandbox.", file=sys.stderr)
            return 1
        sandbox_id = created.id
        created_here = True
        print(f"  Created sandbox: {sandbox_id}  (status: {created.status})")
        print("  Waiting for ready...")
        detail = wait_for_sandbox(
            fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
            target_status="ready",
        )

    print_result("Sandbox before stop", detail)

    # --- Step 3: Stop the sandbox ---
    print_step("Step 3: Stop the sandbox  (ready → stopped)")
    # control plane: POST /v1/sandboxes/{sandbox_id}/stop
    # Stopping releases compute while keeping all data intact.
    stop_result = sandboxes_stop_sandbox.sync(sandbox_id=sandbox_id, client=client)
    print(f"  Stop requested. Current status: {getattr(stop_result, 'status', '?')!r}")

    stopped_detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="stopped",
    )
    print_result("Sandbox after stop", stopped_detail)
    print("  ✓ Sandbox is stopped — compute released, data preserved.")

    # --- Step 4: Start the sandbox ---
    print_step("Step 4: Start the sandbox  (stopped → ready)")
    # control plane: POST /v1/sandboxes/{sandbox_id}/start
    # Starting re-provisions compute and restores the sandbox to ready state.
    start_result = sandboxes_start_sandbox.sync(sandbox_id=sandbox_id, client=client)
    print(f"  Start requested. Current status: {getattr(start_result, 'status', '?')!r}")

    ready_detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="ready",
    )
    print_result("Sandbox after start", ready_detail)
    print("  ✓ Sandbox is ready — data-plane operations can resume.")

    # --- Cleanup ---
    if created_here:
        print_step("Cleanup: deleting temporary sandbox")
        # control plane: DELETE /v1/sandboxes/{sandbox_id}
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=client)
        print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
