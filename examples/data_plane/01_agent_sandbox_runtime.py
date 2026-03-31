"""Data-plane runtime via ``agent_sandbox.Sandbox`` — Inside your sandbox.

Control plane: ``treadstone_sdk`` for lifecycle and scoped data-plane keys.
Data plane: ``agent_sandbox.Sandbox`` with ``base_url=sandbox.urls.proxy``.

Demonstrates shell, file, browser, and Jupyter calls. Mirrors
``web/public/docs/inside-sandbox.md`` (HTTP shapes) using the Python helper SDK.

Usage:
  pip install treadstone-sdk agent-sandbox

  python examples/data_plane/01_agent_sandbox_runtime.py --api-key <key> --sandbox-id <id>
  python examples/data_plane/01_agent_sandbox_runtime.py --api-key <key>
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXAMPLES_ROOT))

from _shared import (  # noqa: E402
    create_data_plane_key,
    get_control_client,
    get_sandbox_client,
    make_sandbox_name,
    parse_args,
    print_result,
    print_section,
    print_step,
    proxy_url_from_detail,
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
        import agent_sandbox  # noqa: F401
    except ImportError:
        print("ERROR: agent-sandbox is not installed. Run: pip install agent-sandbox", file=sys.stderr)
        return 1

    print_section("Data-plane operations (agent_sandbox)")

    print_step("Step 1: Connect to the control plane")
    ctrl = get_control_client(args.base_url, args.api_key)
    print(f"  Connected to {args.base_url}")

    created_here = False
    dp_key_id: str | None = None
    sandbox_id = args.sandbox_id

    try:
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
            name = make_sandbox_name("example-dataplane")
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

        proxy_url = proxy_url_from_detail(detail)
        if not proxy_url:
            print("ERROR: No proxy URL in sandbox detail.", file=sys.stderr)
            return 1
        print(f"  Sandbox ready.  Proxy URL: {proxy_url}")

        print_step("Step 3: Create a data-plane API key (selected sandbox)")
        dp_key_id, dp_key = create_data_plane_key(ctrl, sandbox_id)
        print(f"  Data-plane key created (id: {dp_key_id})")

        print_step("Step 4: Connect agent_sandbox.Sandbox to urls.proxy")
        sb = get_sandbox_client(proxy_url, dp_key)
        print("  Data-plane client ready.")

        print_step("Step 5: Shell — exec_command")
        result = sb.shell.exec_command(command="echo 'Hello from the sandbox!' && uname -a")
        print_result("shell.exec_command", result)

        result2 = sb.shell.exec_command(command="ls /tmp && echo 'exit:' $?")
        print_result("shell.exec_command (ls /tmp)", result2)

        print_step("Step 6: File — write, read, list")
        test_path = "/tmp/treadstone-example-dp.txt"
        content = "Written by examples/data_plane/01_agent_sandbox_runtime.py\n"

        write_result = sb.file.write_file(file=test_path, content=content)
        print_result("file.write_file", write_result)

        read_result = sb.file.read_file(file=test_path)
        print_result("file.read_file", read_result)

        list_result = sb.file.list_path(path="/tmp")
        print_result("file.list_path (/tmp)", list_result)

        print_step("Step 7: Browser — info and screenshot")
        browser_info = sb.browser.get_info()
        print_result("browser.get_info", browser_info)

        screenshot_bytes = sb.browser.screenshot()
        if screenshot_bytes:
            screenshot_path = "/tmp/treadstone-example-screenshot.png"
            with open(screenshot_path, "wb") as f:
                if isinstance(screenshot_bytes, bytes):
                    f.write(screenshot_bytes)
                else:
                    f.write(base64.b64decode(screenshot_bytes))
            print(f"  Screenshot saved inside sandbox at: {screenshot_path}")
        else:
            print("  (No screenshot returned — browser may not be available in this template)")

        print_step("Step 8: Jupyter — execute_code")
        code = """
import sys
import math

print(f"Python {sys.version}")
print(f"Pi ≈ {math.pi:.6f}")
result = [x**2 for x in range(1, 6)]
print(f"Squares: {result}")
result
"""
        jupyter_result = sb.jupyter.execute_code(code=code)
        print_result("jupyter.execute_code", jupyter_result)

        print("\n  ✓ All data-plane operations completed successfully.")

    finally:
        print_step("Cleanup")
        if dp_key_id:
            auth_delete_api_key.sync(key_id=dp_key_id, client=ctrl)
            print(f"  Data-plane API key {dp_key_id} deleted.")
        if created_here and sandbox_id:
            sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=ctrl)
            print(f"  Sandbox {sandbox_id} deleted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
