"""Example 04 — Data-Plane Operations

This example shows how to interact with a sandbox's internal runtime after it
has been created and is in "ready" state.

Architecture recap
------------------
  Control plane (Treadstone API)   — manages sandbox lifecycle
  Data plane   (Sandbox runtime)   — executes work *inside* a sandbox

The two planes use two different SDK clients:

  treadstone_sdk.AuthenticatedClient  ← control plane  (lifecycle, keys)
  agent_sandbox.Sandbox               ← data plane     (shell, file, browser, jupyter)

Connecting them:
  1. Get sandbox_detail.urls.proxy from the control-plane API.
  2. Create a data-plane API key scoped to this sandbox.
  3. Pass both to agent_sandbox.Sandbox(base_url=proxy_url, headers={...}).

Operations covered in this example:
  • Shell  — execute commands, capture output
  • File   — write, read, list directory contents
  • Browser — get browser info, take a screenshot
  • Jupyter — run Python code, capture outputs

Usage:
  pip install treadstone-sdk agent-sandbox

  # Use an existing ready sandbox:
  python examples/04_data_plane.py --api-key <key> --sandbox-id <id>

  # Create a temporary sandbox (slower, but fully self-contained):
  python examples/04_data_plane.py --api-key <key>
"""

from __future__ import annotations

import base64
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from _shared import (
    _get,
    create_data_plane_key,
    get_control_client,
    get_sandbox_client,
    make_sandbox_name,
    parse_args,
    print_result,
    print_section,
    print_step,
    wait_for_sandbox,
)


def main() -> int:
    args = parse_args("Run data-plane operations (shell, file, browser, jupyter) inside a sandbox.")

    try:
        from treadstone_sdk.api.auth import auth_delete_api_key
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_delete_sandbox,
            sandboxes_get_sandbox,
        )
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
    except ImportError:
        print("ERROR: treadstone-sdk is not installed. Run: pip install treadstone-sdk", file=sys.stderr)
        return 1

    try:
        import agent_sandbox  # noqa: F401 — validate import before proceeding
    except ImportError:
        print("ERROR: agent-sandbox is not installed. Run: pip install agent-sandbox", file=sys.stderr)
        return 1

    print_section("Data-Plane Operations")

    # -------------------------------------------------------------------------
    # Step 1: Connect to the control plane
    # -------------------------------------------------------------------------
    print_step("Step 1: Connect to the control plane")
    # control plane: all lifecycle and key management calls go here
    ctrl = get_control_client(args.base_url, args.api_key)
    print(f"  Connected to {args.base_url}")

    created_here = False
    dp_key_id: str | None = None
    sandbox_id = args.sandbox_id

    try:
        # -------------------------------------------------------------------------
        # Step 2: Resolve a ready sandbox
        # -------------------------------------------------------------------------
        print_step("Step 2: Resolve a ready sandbox")
        if sandbox_id:
            print(f"  Using existing sandbox: {sandbox_id}")
            detail = sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl)
            if not isinstance(detail, SandboxDetailResponse):
                print(f"ERROR: Sandbox {sandbox_id} not found.", file=sys.stderr)
                return 1
            if detail.status != "ready":
                print(f"  Sandbox is {detail.status!r} — waiting for ready...")
                detail = wait_for_sandbox(
                    fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl),
                    target_status="ready",
                )
        else:
            print("  No --sandbox-id provided; creating a temporary sandbox.")
            name = make_sandbox_name("example-04")
            created = sandboxes_create_sandbox.sync(
                client=ctrl,
                body=CreateSandboxRequest(template=args.template, name=name),
            )
            if not isinstance(created, SandboxResponse):
                print("ERROR: Failed to create sandbox.", file=sys.stderr)
                return 1
            sandbox_id = created.id
            created_here = True
            print(f"  Created sandbox: {sandbox_id}  (status: {created.status})")
            detail = wait_for_sandbox(
                fetch_fn=lambda: sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=ctrl),
                target_status="ready",
            )

        proxy_url = _get(detail, "urls", "proxy")
        if not proxy_url:
            print("ERROR: No proxy URL in sandbox detail.", file=sys.stderr)
            return 1
        print(f"  Sandbox ready.  Proxy URL: {proxy_url}")

        # -------------------------------------------------------------------------
        # Step 3: Create a data-plane API key scoped to this sandbox
        # -------------------------------------------------------------------------
        print_step("Step 3: Create a data-plane API key")
        # The data-plane key grants access only to this sandbox's runtime.
        # It is separate from your control-plane key for security isolation.
        #
        # control plane: POST /v1/auth/api-keys  (scope: data_plane, selected sandbox)
        dp_key_id, dp_key = create_data_plane_key(ctrl, sandbox_id)
        print(f"  Data-plane key created (id: {dp_key_id})")

        # -------------------------------------------------------------------------
        # Step 4: Build the data-plane client
        # -------------------------------------------------------------------------
        print_step("Step 4: Connect to the data plane")
        # data plane: agent_sandbox.Sandbox uses proxy_url as its base URL.
        # All subsequent operations go directly to the sandbox runtime via the
        # Treadstone proxy — no control-plane involvement needed.
        sb = get_sandbox_client(proxy_url, dp_key)
        print("  Data-plane client ready.")

        # -------------------------------------------------------------------------
        # Step 5: Shell operations
        # -------------------------------------------------------------------------
        print_step("Step 5: Shell — execute commands")
        # data plane: POST /v1/shell/exec
        # Runs a shell command inside the sandbox and returns stdout/stderr/exit code.
        result = sb.shell.exec_command(command="echo 'Hello from the sandbox!' && uname -a")
        print_result("shell.exec_command", result)

        # Run a multi-step command and capture the output
        result2 = sb.shell.exec_command(command="ls /tmp && echo 'exit:' $?")
        print_result("shell.exec_command (ls /tmp)", result2)

        # -------------------------------------------------------------------------
        # Step 6: File operations
        # -------------------------------------------------------------------------
        print_step("Step 6: File — write, read, list")
        test_path = "/tmp/example-04-test.txt"
        content = "Written by Treadstone example 04\nLine 2\nLine 3\n"

        # data plane: POST /v1/file/write
        write_result = sb.file.write_file(file=test_path, content=content)
        print_result("file.write_file", write_result)

        # data plane: POST /v1/file/read
        read_result = sb.file.read_file(file=test_path)
        print_result("file.read_file", read_result)

        # data plane: POST /v1/file/list
        list_result = sb.file.list_path(path="/tmp")
        print_result("file.list_path (/tmp)", list_result)

        # -------------------------------------------------------------------------
        # Step 7: Browser operations
        # -------------------------------------------------------------------------
        print_step("Step 7: Browser — info and screenshot")
        # data plane: GET /v1/browser/info
        # Returns CDP URL, VNC URL, and current viewport size.
        browser_info = sb.browser.get_info()
        print_result("browser.get_info", browser_info)

        # data plane: GET /v1/browser/screenshot
        # Returns a PNG image of the current browser viewport.
        screenshot_bytes = sb.browser.screenshot()
        if screenshot_bytes:
            screenshot_path = "/tmp/example-04-screenshot.png"
            with open(screenshot_path, "wb") as f:
                if isinstance(screenshot_bytes, bytes):
                    f.write(screenshot_bytes)
                else:
                    # Some SDK versions return base64-encoded strings.
                    f.write(base64.b64decode(screenshot_bytes))
            print(f"  Screenshot saved to: {screenshot_path}")
        else:
            print("  (No screenshot returned — browser may not be available in this template)")

        # -------------------------------------------------------------------------
        # Step 8: Jupyter operations
        # -------------------------------------------------------------------------
        print_step("Step 8: Jupyter — execute Python code")
        # data plane: POST /v1/jupyter/execute
        # Runs Python code in a persistent Jupyter kernel session.
        # The session_id keeps variable state across multiple requests.
        code = """
import sys
import math

print(f"Python {sys.version}")
print(f"Pi ≈ {math.pi:.6f}")

# Variables persist across calls within the same session_id.
result = [x**2 for x in range(1, 6)]
print(f"Squares: {result}")
result
"""
        jupyter_result = sb.jupyter.execute_code(code=code)
        print_result("jupyter.execute_code", jupyter_result)

        print("\n  ✓ All data-plane operations completed successfully.")

    finally:
        # -------------------------------------------------------------------------
        # Cleanup: delete ephemeral resources
        # -------------------------------------------------------------------------
        print_step("Cleanup")
        if dp_key_id:
            # control plane: DELETE /v1/auth/api-keys/{id}
            auth_delete_api_key.sync(key_id=dp_key_id, client=ctrl)
            print(f"  Data-plane API key {dp_key_id} deleted.")
        if created_here and sandbox_id:
            # control plane: DELETE /v1/sandboxes/{sandbox_id}
            sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=ctrl)
            print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
