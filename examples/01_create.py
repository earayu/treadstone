"""Example 01 — Create a Sandbox

This example demonstrates the control-plane workflow for creating a sandbox:

  1. List available sandbox templates.
  2. Create a new sandbox from a chosen template.
  3. Poll until the sandbox reaches "ready" status.
  4. Print the sandbox detail, including the proxy URL used to access the data plane.

Usage:
  pip install treadstone-sdk
  python examples/01_create.py --api-key <key> [--template aio-sandbox-tiny]

The sandbox will be deleted automatically when the script finishes unless you
pass --keep to leave it running.
"""

from __future__ import annotations

import argparse
import sys

# Add examples/ to path so _shared is importable when run directly.
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
    # --- Parse arguments ---
    base_args = parse_args("Create a Treadstone sandbox and wait for it to be ready.")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--keep", action="store_true", help="Do not delete the sandbox after creation.")
    extra, _ = parser.parse_known_args()

    try:
        from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
        from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox, sandboxes_delete_sandbox, sandboxes_get_sandbox
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
        from treadstone_sdk.models.sandbox_template_list_response import SandboxTemplateListResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    # --- Step 1: Connect to the control plane ---
    print_section("Create Sandbox")
    print_step("Step 1: Connect to the control plane")
    # control plane: manages sandbox lifecycle (create, list, start, stop, delete)
    client = get_control_client(base_args.base_url, base_args.api_key)
    print(f"  Connected to {base_args.base_url}")

    # --- Step 2: List available templates ---
    print_step("Step 2: List available sandbox templates")
    # Each template defines the OS image, pre-installed tools, and resource limits.
    templates = sandbox_templates_list_sandbox_templates.sync(client=client)
    if not isinstance(templates, SandboxTemplateListResponse):
        print("ERROR: Failed to list templates.", file=sys.stderr)
        return 1

    available = [t.name for t in (templates.items or [])]
    print(f"  Available templates: {', '.join(available) or '(none)'}")

    if base_args.template not in available:
        print(f"ERROR: Template '{base_args.template}' not found.", file=sys.stderr)
        return 1

    # --- Step 3: Create the sandbox ---
    print_step("Step 3: Create the sandbox")
    name = make_sandbox_name("example-01")
    print(f"  Sandbox name : {name}")
    print(f"  Template     : {base_args.template}")

    # control plane: POST /v1/sandboxes — returns immediately with status "creating"
    created = sandboxes_create_sandbox.sync(
        client=client,
        body=CreateSandboxRequest(template=base_args.template, name=name),
    )
    if not isinstance(created, SandboxResponse):
        print("ERROR: Failed to create sandbox.", file=sys.stderr)
        return 1

    sandbox_id = created.id
    print(f"  Sandbox ID   : {sandbox_id}")
    print(f"  Status       : {created.status}  (will transition to 'ready')")

    # --- Step 4: Wait until ready ---
    print_step("Step 4: Poll until status = 'ready'")
    # control plane: GET /v1/sandboxes/{sandbox_id}
    detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="ready",
    )
    if not isinstance(detail, SandboxDetailResponse):
        print("ERROR: Unexpected response type while polling.", file=sys.stderr)
        return 1

    # --- Step 5: Inspect the result ---
    print_step("Step 5: Sandbox is ready")
    print_result("Sandbox detail", detail)

    # The proxy URL is the gateway to all data-plane operations.
    # Pass it as base_url to agent_sandbox.Sandbox() in your data-plane code.
    proxy_url = getattr(getattr(detail, "urls", None), "proxy", None)
    if proxy_url:
        print(f"\n  Data-plane proxy URL: {proxy_url}")
        print("  → Pass this URL to agent_sandbox.Sandbox(base_url=...) to run shell/file/browser commands.")

    # --- Cleanup ---
    if not extra.keep:
        print_step("Cleanup: deleting sandbox")
        # control plane: DELETE /v1/sandboxes/{sandbox_id}
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=client)
        print(f"  Sandbox {sandbox_id} deleted.")
    else:
        print(f"\n  --keep flag set: sandbox {sandbox_id} is still running.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
