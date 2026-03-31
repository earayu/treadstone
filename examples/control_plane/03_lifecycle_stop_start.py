"""Stop and start a sandbox (control plane) — Sandbox Lifecycle.

Status path: ready → (stop) → stopped → (start) → ready.

Public docs: ``web/public/docs/sandbox-lifecycle.md``.

Usage:
  pip install treadstone-sdk

  python examples/control_plane/03_lifecycle_stop_start.py --api-key <key> --sandbox-id <id>
  python examples/control_plane/03_lifecycle_stop_start.py --api-key <key>
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXAMPLES_ROOT))

from _shared import (  # noqa: E402
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

    print_step("Step 1: Connect to the control plane")
    client = get_control_client(args.base_url, args.api_key)
    print(f"  Connected to {args.base_url}")

    created_here = False
    sandbox_id = args.sandbox_id

    print_step("Step 2: Resolve target sandbox")
    if sandbox_id:
        print(f"  Using existing sandbox: {sandbox_id}")
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
        print("  No --sandbox-id provided; creating a temporary sandbox.")
        name = make_sandbox_name("example-lifecycle")
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

    print_step("Step 3: Stop the sandbox  (ready → stopped)")
    stop_result = sandboxes_stop_sandbox.sync(sandbox_id=sandbox_id, client=client)
    print(f"  Stop requested. Current status: {getattr(stop_result, 'status', '?')!r}")

    stopped_detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="stopped",
    )
    print_result("Sandbox after stop", stopped_detail)
    print("  ✓ Sandbox is stopped — compute released, data preserved.")

    print_step("Step 4: Start the sandbox  (stopped → ready)")
    start_result = sandboxes_start_sandbox.sync(sandbox_id=sandbox_id, client=client)
    print(f"  Start requested. Current status: {getattr(start_result, 'status', '?')!r}")

    ready_detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="ready",
    )
    print_result("Sandbox after start", ready_detail)
    print("  ✓ Sandbox is ready — data-plane operations can resume.")

    if created_here:
        print_step("Cleanup: deleting temporary sandbox")
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=client)
        print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
