"""Browser handoff URLs (control plane) — issue and revoke ``open_link``.

Maps to ``POST/GET/DELETE /v1/sandboxes/{id}/web-link`` (CLI: ``treadstone sandboxes web …``).

Public docs: ``web/public/docs/browser-handoff.md``.

Usage:
  pip install treadstone-sdk

  python examples/control_plane/04_browser_handoff.py --api-key <key> --sandbox-id <id>
  python examples/control_plane/04_browser_handoff.py --api-key <key>
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
    args = parse_args("Create a handoff link, read status, disable, and create a fresh link.")

    try:
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_create_sandbox_web_link,
            sandboxes_delete_sandbox,
            sandboxes_delete_sandbox_web_link,
            sandboxes_get_sandbox,
            sandboxes_get_sandbox_web_link,
        )
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
        from treadstone_sdk.models.sandbox_web_link_response import SandboxWebLinkResponse
        from treadstone_sdk.models.sandbox_web_link_status_response import SandboxWebLinkStatusResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    print_section("Browser handoff (web-link)")

    print_step("Step 1: Connect to the control plane")
    client = get_control_client(args.base_url, args.api_key)
    print(f"  Connected to {args.base_url}")

    created_here = False
    sandbox_id = args.sandbox_id

    print_step("Step 2: Resolve a ready sandbox")
    if sandbox_id:
        print(f"  Using existing sandbox: {sandbox_id}")
        detail = sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client)
        if not isinstance(detail, SandboxDetailResponse):
            print(f"ERROR: Sandbox {sandbox_id} not found.", file=sys.stderr)
            return 1
        if detail.status != "ready":
            print(f"  Sandbox is {detail.status!r} — waiting for ready...")
            detail = wait_for_sandbox(
                fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
                target_status="ready",
            )
    else:
        print("  No --sandbox-id provided; creating a temporary sandbox.")
        name = make_sandbox_name("example-handoff")
        created = sandboxes_create_sandbox.sync(
            client=client,
            body=CreateSandboxRequest(template=args.template, name=name),
        )
        if not isinstance(created, SandboxResponse):
            print("ERROR: Failed to create sandbox.", file=sys.stderr)
            return 1
        sandbox_id = created.id
        created_here = True
        print(f"  Created sandbox: {sandbox_id}")
        wait_for_sandbox(
            fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
            target_status="ready",
        )

    print_step("Step 3: Enable handoff — POST /v1/sandboxes/{id}/web-link")
    session = sandboxes_create_sandbox_web_link.sync(sandbox_id=sandbox_id, client=client)
    if not isinstance(session, SandboxWebLinkResponse):
        print("ERROR: Unexpected response from web-link create.", file=sys.stderr)
        return 1
    print_result("Handoff session (open_link, web_url, expires_at)", session)
    print("\n  open_link — shareable URL (token in query). Do not guess this; always from the API.")

    print_step("Step 4: Handoff status — GET /v1/sandboxes/{id}/web-link")
    status = sandboxes_get_sandbox_web_link.sync(sandbox_id=sandbox_id, client=client)
    if not isinstance(status, SandboxWebLinkStatusResponse):
        print("ERROR: Unexpected response from web-link status.", file=sys.stderr)
        return 1
    print_result("Status (enabled, web_url, expires_at, last_used_at — no open_link here)", status)

    print_step("Step 5: Revoke — DELETE /v1/sandboxes/{id}/web-link")
    sandboxes_delete_sandbox_web_link.sync(sandbox_id=sandbox_id, client=client)
    print("  Handoff disabled.")

    print_step("Step 6: Issue a fresh link — POST web-link again")
    session2 = sandboxes_create_sandbox_web_link.sync(sandbox_id=sandbox_id, client=client)
    if not isinstance(session2, SandboxWebLinkResponse):
        print("ERROR: Unexpected response on second web-link create.", file=sys.stderr)
        return 1
    print_result("New handoff session", session2)

    if created_here:
        print_step("Cleanup: deleting temporary sandbox")
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=client)
        print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
