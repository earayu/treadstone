"""Minimal data-plane HTTP call with httpx — REST / Inside-your-sandbox pattern.

Uses ``urls.proxy`` from the control plane and ``Authorization: Bearer`` with an
API key that has data-plane access (default keys include both planes).

Sends ``POST /v1/shell/exec`` (same route family as
``web/public/docs/inside-sandbox.md``). A plain ``GET /health`` is not used here
because workloads may not expose it (404 from nginx is common).

This does **not** use ``agent-sandbox``. See ``01_agent_sandbox_runtime.py`` for
the high-level client.

Public docs: ``web/public/docs/rest-api-guide.md``, ``inside-sandbox.md``.

Usage:
  pip install treadstone-sdk httpx

  python examples/data_plane/02_httpx_proxy_shell_exec.py --api-key <key> --sandbox-id <id>
  python examples/data_plane/02_httpx_proxy_shell_exec.py --api-key <key>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXAMPLES_ROOT))

from _shared import (  # noqa: E402
    get_control_client,
    make_sandbox_name,
    parse_args,
    print_section,
    print_step,
    wait_for_sandbox,
)


def main() -> int:
    args = parse_args("POST /v1/shell/exec via the sandbox proxy using httpx (data plane).")

    try:
        import httpx
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_delete_sandbox,
            sandboxes_get_sandbox,
        )
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
    except ImportError as e:
        print(
            "ERROR: need treadstone-sdk and httpx. Run: pip install treadstone-sdk httpx",
            file=sys.stderr,
        )
        print(e, file=sys.stderr)
        return 1

    print_section("Data plane: httpx → proxy → POST /v1/shell/exec")

    print_step("Step 1: Control plane — get urls.proxy")
    ctrl = get_control_client(args.base_url, args.api_key)
    created_here = False
    sandbox_id = args.sandbox_id

    if sandbox_id:
        detail = sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl)
        if not isinstance(detail, SandboxDetailResponse):
            print(f"ERROR: Sandbox {sandbox_id} not found.", file=sys.stderr)
            return 1
        if detail.status != "ready":
            detail = wait_for_sandbox(
                fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl),
                target_status="ready",
            )
    else:
        name = make_sandbox_name("example-httpx")
        created = sandboxes_create_sandbox.sync(
            client=ctrl,
            body=CreateSandboxRequest(template=args.template, name=name),
        )
        if not isinstance(created, SandboxResponse):
            print("ERROR: Failed to create sandbox.", file=sys.stderr)
            return 1
        sandbox_id = created.id
        created_here = True
        detail = wait_for_sandbox(
            fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl),
            target_status="ready",
        )

    proxy_base = detail.urls.proxy if detail.urls else None
    if not proxy_base:
        print("ERROR: sandbox detail has no urls.proxy", file=sys.stderr)
        return 1
    print(f"  sandbox_id: {sandbox_id}")
    print(f"  proxy base: {proxy_base}")

    print_step("Step 2: Data plane — POST /v1/shell/exec")
    base = proxy_base.rstrip("/")
    payload = {
        "command": "echo treadstone-httpx-example && uname -s",
        "exec_dir": "/tmp",
    }
    with httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {args.api_key}"},
        timeout=60.0,
    ) as client:
        response = client.post("/v1/shell/exec", json=payload)

    print(f"  HTTP {response.status_code}")
    try:
        body = response.json()
        print(f"  body:\n{json.dumps(body, indent=2)}")
    except json.JSONDecodeError:
        print(f"  body (raw): {response.text[:800]!r}")

    if response.status_code >= 400:
        return 1

    if created_here:
        print_step("Cleanup: deleting temporary sandbox")
        sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=ctrl)
        print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
