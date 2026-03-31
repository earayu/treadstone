"""Shared helpers for Treadstone examples.

Provides thin wrappers around the Treadstone SDK and agent-sandbox SDK so that
each example file can stay focused on a single concept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from typing import Any

DEFAULT_BASE_URL = "https://api.treadstone-ai.dev"
DEFAULT_TEMPLATE = "aio-sandbox-tiny"
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_READY_TIMEOUT = 600.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def parse_args(description: str, *, name_prefix: str = "example") -> argparse.Namespace:
    """Parse common CLI arguments shared by all examples."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TREADSTONE_BASE_URL", DEFAULT_BASE_URL),
        help=f"Treadstone API base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("TREADSTONE_API_KEY"),
        help="Control-plane API key (env: TREADSTONE_API_KEY).",
    )
    parser.add_argument(
        "--template",
        default=os.environ.get("TREADSTONE_TEMPLATE", DEFAULT_TEMPLATE),
        help=f"Sandbox template name (default: {DEFAULT_TEMPLATE}).",
    )
    parser.add_argument(
        "--sandbox-id",
        default=os.environ.get("TREADSTONE_SANDBOX_ID"),
        help="Existing sandbox ID (skips creation where supported).",
    )
    args = parser.parse_args()
    if not args.api_key:
        parser.error(
            "An API key is required. Provide --api-key or set TREADSTONE_API_KEY."
        )
    args.base_url = args.base_url.rstrip("/")
    return args


def make_sandbox_name(prefix: str = "example") -> str:
    """Generate a unique, DNS-safe sandbox name."""
    sanitized = re.sub(r"[^a-z0-9-]+", "-", prefix.lower()).strip("-") or "example"
    timestamp = time.strftime("%m%d%H%M%S", time.gmtime())
    suffix = uuid.uuid4().hex[:6]
    raw = f"{sanitized}-{timestamp}-{suffix}"
    return raw[:55].rstrip("-")


# ---------------------------------------------------------------------------
# Control-plane client
# ---------------------------------------------------------------------------


def get_control_client(base_url: str, api_key: str) -> Any:
    """Return an authenticated Treadstone SDK client for control-plane operations."""
    try:
        from treadstone_sdk import AuthenticatedClient
    except ImportError:
        _abort("treadstone-sdk is not installed. Run: pip install treadstone-sdk")
    return AuthenticatedClient(base_url=base_url, token=api_key, follow_redirects=True)


# ---------------------------------------------------------------------------
# Sandbox state helpers
# ---------------------------------------------------------------------------


def wait_for_sandbox(
    fetch_fn: Any,
    target_status: str,
    *,
    timeout: float = DEFAULT_READY_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
) -> Any:
    """Poll *fetch_fn()* until ``status == target_status`` or timeout is reached.

    Args:
        fetch_fn: A zero-argument callable that returns a sandbox detail object.
        target_status: The ``SandboxStatus`` string to wait for (e.g. ``"ready"``).
        timeout: Maximum seconds to wait before raising ``TimeoutError``.
        poll_interval: Seconds between polls.

    Returns:
        The sandbox detail object once it reaches *target_status*.
    """
    terminal_statuses = {"error", "deleted"}
    deadline = time.monotonic() + timeout
    while True:
        detail = fetch_fn()
        status = _get(detail, "status") or ""
        sandbox_id = _get(detail, "id") or "?"
        message = _get(detail, "status_message") or ""
        print(f"  [poll] sandbox {sandbox_id}: status={status!r}" + (f" — {message}" if message else ""))
        if status == target_status:
            return detail
        if status in terminal_statuses:
            raise RuntimeError(
                f"Sandbox {sandbox_id} reached terminal status {status!r}: {message}"
            )
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Timed out waiting for sandbox {sandbox_id} to reach {target_status!r}."
            )
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# Data-plane helpers
# ---------------------------------------------------------------------------


def create_data_plane_key(control_client: Any, sandbox_id: str) -> str:
    """Create a sandbox-scoped data-plane API key and return the key string.

    The key grants access *only* to the specified sandbox's data plane.
    """
    try:
        from treadstone_sdk.api.auth import auth_create_api_key
        from treadstone_sdk.models.api_key_data_plane_mode import ApiKeyDataPlaneMode
        from treadstone_sdk.models.api_key_data_plane_scope import ApiKeyDataPlaneScope
        from treadstone_sdk.models.api_key_response import ApiKeyResponse
        from treadstone_sdk.models.api_key_scope import ApiKeyScope
        from treadstone_sdk.models.create_api_key_request import CreateApiKeyRequest
    except ImportError:
        _abort("treadstone-sdk is not installed. Run: pip install treadstone-sdk")

    scope = ApiKeyScope(
        control_plane=False,
        data_plane=ApiKeyDataPlaneScope(
            mode=ApiKeyDataPlaneMode.SELECTED,
            sandbox_ids=[sandbox_id],
        ),
    )
    result = auth_create_api_key.sync(
        client=control_client,
        body=CreateApiKeyRequest(name=f"example-dp-{sandbox_id[:8]}", scope=scope),
    )
    if not isinstance(result, ApiKeyResponse) or not result.key:
        raise RuntimeError("Failed to create data-plane API key.")
    return result.key


def get_sandbox_client(proxy_url: str, data_plane_key: str) -> Any:
    """Return an agent-sandbox ``Sandbox`` client pointed at the proxy URL.

    The ``proxy_url`` comes from ``sandbox_detail.urls.proxy`` and acts as the
    base URL for all sandbox-internal operations (shell, file, browser, etc.).

    Args:
        proxy_url: Value of ``sandbox_detail.urls.proxy``.
        data_plane_key: A data-plane API key scoped to this sandbox.
    """
    try:
        from agent_sandbox import Sandbox
    except ImportError:
        _abort("agent-sandbox is not installed. Run: pip install agent-sandbox")
    return Sandbox(
        base_url=proxy_url.rstrip("/"),
        headers={"Authorization": f"Bearer {data_plane_key}"},
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_step(label: str) -> None:
    print(f"\n--- {label} ---")


def print_result(label: str, data: Any) -> None:
    print(f"{label}:")
    print(json.dumps(_to_serializable(data), indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _get(obj: Any, *keys: str) -> Any:
    """Traverse a chain of attribute or dict lookups, returning None on any miss."""
    current = obj
    for key in keys:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current


def _to_serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(i) for i in value]
    for method in ("to_dict", "dict", "model_dump"):
        fn = getattr(value, method, None)
        if callable(fn):
            return _to_serializable(fn())
    if hasattr(value, "__dict__"):
        return {k: _to_serializable(v) for k, v in vars(value).items() if not k.startswith("_")}
    return repr(value)


def _abort(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)
