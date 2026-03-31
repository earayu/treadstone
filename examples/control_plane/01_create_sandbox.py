"""Create a sandbox (control plane) — Quickstart / Sandbox Lifecycle.

Steps:
  1. List sandbox templates.
  2. Create a sandbox from a template.
  3. Poll until status is ``ready``.
  4. Print detail including ``urls.proxy`` for the data plane.

Public docs: ``web/public/docs/quickstart.md``, ``sandbox-lifecycle.md``.

Usage:
  pip install treadstone-sdk
  python examples/control_plane/01_create_sandbox.py --api-key <key> [--template aio-sandbox-tiny]

The sandbox is deleted when the script exits unless you pass ``--keep``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXAMPLES_ROOT))

from _shared import (  # noqa: E402
    get_control_client,
    make_sandbox_name,
    parse_base_args,
    print_result,
    print_section,
    print_step,
    wait_for_sandbox,
)


def main() -> int:
    base_args, rest = parse_base_args("Create a Treadstone sandbox and wait for it to be ready.")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--keep", action="store_true", help="Do not delete the sandbox after creation.")
    extra = parser.parse_args(rest)

    try:
        from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_delete_sandbox,
            sandboxes_get_sandbox,
        )
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
        from treadstone_sdk.models.sandbox_template_list_response import SandboxTemplateListResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    print_section("Create Sandbox")
    print_step("Step 1: Connect to the control plane")
    client = get_control_client(base_args.base_url, base_args.api_key)
    print(f"  Connected to {base_args.base_url}")

    print_step("Step 2: List available sandbox templates")
    templates = sandbox_templates_list_sandbox_templates.sync(client=client)
    if not isinstance(templates, SandboxTemplateListResponse):
        print("ERROR: Failed to list templates.", file=sys.stderr)
        return 1

    available = [t.name for t in (templates.items or [])]
    print(f"  Available templates: {', '.join(available) or '(none)'}")

    if base_args.template not in available:
        print(f"ERROR: Template '{base_args.template}' not found.", file=sys.stderr)
        return 1

    print_step("Step 3: Create the sandbox")
    name = make_sandbox_name("example-create")
    print(f"  Sandbox name : {name}")
    print(f"  Template     : {base_args.template}")

    created = sandboxes_create_sandbox.sync(
        client=client,
        body=CreateSandboxRequest(template=base_args.template, name=name),
    )
    if not isinstance(created, SandboxResponse):
        print("ERROR: Failed to create sandbox.", file=sys.stderr)
        return 1

    sandbox_id = created.id
    print(f"  Sandbox ID   : {sandbox_id}")
    print(f"  Status       : {created.status}")

    print_step("Step 4: Poll until status = 'ready'")
    detail = wait_for_sandbox(
        fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client),
        target_status="ready",
    )
    if not isinstance(detail, SandboxDetailResponse):
        print("ERROR: Unexpected response type while polling.", file=sys.stderr)
        return 1

    print_step("Step 5: Sandbox is ready")
    print_result("Sandbox detail", detail)

    proxy_url = getattr(getattr(detail, "urls", None), "proxy", None)
    if proxy_url:
        print(f"\n  Data-plane proxy URL: {proxy_url}")
        print("  → Use this as base_url for agent_sandbox.Sandbox or httpx (see examples/data_plane/).")

    if not extra.keep:
        print_step("Cleanup: deleting sandbox")
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=client)
        print(f"  Sandbox {sandbox_id} deleted.")
    else:
        print(f"\n  --keep flag set: sandbox {sandbox_id} is still running.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
