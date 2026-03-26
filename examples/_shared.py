from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.treadstone-ai.dev"
DEFAULT_TEMPLATE = "aio-sandbox-tiny"
DEFAULT_TIMEOUT_SECONDS = 30.0
READY_STATUS = "ready"
FAILED_STATUSES = {"error", "failed", "deleted"}


@dataclass(slots=True)
class ExampleConfig:
    base_url: str
    template: str
    email: str | None
    password: str | None
    api_key: str | None
    keep_sandbox: bool
    keep_keys: bool
    name_prefix: str


@dataclass(slots=True)
class TemporaryApiKey:
    id: str
    key: str
    label: str


def parse_common_args(*, description: str, name_prefix: str) -> ExampleConfig:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TREADSTONE_BASE_URL", DEFAULT_BASE_URL),
        help=f"Treadstone base URL. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--template",
        default=os.environ.get("TREADSTONE_TEMPLATE", DEFAULT_TEMPLATE),
        help=f"Sandbox template name. Defaults to {DEFAULT_TEMPLATE}.",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("TREADSTONE_EMAIL"),
        help="Email used for register/login when --api-key is not provided.",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TREADSTONE_PASSWORD"),
        help="Password used for register/login when --api-key is not provided.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("TREADSTONE_API_KEY"),
        help="Existing control-plane API key. Skips register/login/bootstrap key creation.",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Skip sandbox deletion during cleanup.",
    )
    parser.add_argument(
        "--keep-keys",
        action="store_true",
        help="Skip deletion of any temporary API keys created by the example.",
    )
    args = parser.parse_args()

    config = ExampleConfig(
        base_url=normalize_url(args.base_url),
        template=args.template,
        email=args.email,
        password=args.password,
        api_key=args.api_key,
        keep_sandbox=args.keep_sandbox,
        keep_keys=args.keep_keys,
        name_prefix=name_prefix,
    )

    if config.api_key is None and (not config.email or not config.password):
        parser.error(
            "Provide --api-key or set both --email and --password "
            "(or TREADSTONE_API_KEY / TREADSTONE_EMAIL / TREADSTONE_PASSWORD)."
        )

    return config


def normalize_url(url: str) -> str:
    return url.rstrip("/")


def build_raw_data_plane_base(proxy_url: str) -> str:
    return f"{normalize_url(proxy_url)}/v1"


def build_sdk_data_plane_base(proxy_url: str) -> str:
    return normalize_url(proxy_url)


def make_sandbox_name(prefix: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]+", "-", prefix.lower()).strip("-") or "example"
    timestamp = time.strftime("%m%d%H%M%S", time.gmtime())
    suffix = uuid.uuid4().hex[:8]
    raw_name = f"{sanitized}-{timestamp}-{suffix}"
    return raw_name[:55].rstrip("-")


def print_header(title: str) -> None:
    print(f"\n== {title} ==")


def print_step(message: str) -> None:
    print(f"[step] {message}")


def print_note(message: str) -> None:
    print(f"[info] {message}")


def print_json(label: str, payload: Any) -> None:
    print(f"{label}:")
    print(json.dumps(to_serializable(payload), indent=2, sort_keys=True))


def to_serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(item) for item in value]

    for method_name in ("to_dict", "dict", "model_dump"):
        method = getattr(value, method_name, None)
        if callable(method):
            return to_serializable(method())

    if hasattr(value, "__dict__"):
        return {
            key: to_serializable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }

    return repr(value)


def get_value(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(key)
            continue
        current = getattr(current, key, None)
    return current


def ensure_template_exists(templates: Any, template_name: str) -> None:
    items = get_value(templates, "items") or []
    available = [get_value(item, "name") for item in items]
    if template_name not in available:
        joined = ", ".join(name for name in available if name)
        raise RuntimeError(f"Template '{template_name}' is not available. Found: {joined or 'none'}")


def new_http_client(base_url: str, *, api_key: str | None = None) -> httpx.Client:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(
        base_url=normalize_url(base_url),
        headers=headers,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    label: str,
    expected_statuses: int | Iterable[int],
    quiet: bool = False,
    **kwargs: Any,
) -> Any:
    expected = {expected_statuses} if isinstance(expected_statuses, int) else set(expected_statuses)
    response = client.request(method, url, **kwargs)

    if response.status_code not in expected:
        detail = response.text[:1_200]
        raise RuntimeError(
            f"{label} failed with HTTP {response.status_code}.\n"
            f"Expected one of {sorted(expected)}.\n"
            f"Response body:\n{detail}"
        )

    if not quiet:
        print_note(f"{label}: HTTP {response.status_code}")

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} returned non-JSON content.") from exc


def login_or_register(client: httpx.Client, config: ExampleConfig) -> None:
    payload = {"email": config.email, "password": config.password}
    if payload["email"] is None or payload["password"] is None:
        raise RuntimeError("Email and password are required for register/login.")

    print_step("Attempting login with email/password")
    response = client.post("/v1/auth/login", json=payload)
    if response.status_code == 200:
        print_note("Login succeeded")
        return

    if response.status_code != 400:
        raise RuntimeError(f"Login failed with HTTP {response.status_code}: {response.text[:1_200]}")

    print_step("Login failed, attempting registration")
    register_response = client.post("/v1/auth/register", json=payload)
    if register_response.status_code == 201:
        print_note("Registration succeeded")
    elif register_response.status_code == 409:
        raise RuntimeError(
            "Login failed and registration hit a conflict. "
            "Verify TREADSTONE_EMAIL/TREADSTONE_PASSWORD or provide TREADSTONE_API_KEY."
        )
    else:
        raise RuntimeError(
            f"Registration failed with HTTP {register_response.status_code}: {register_response.text[:1_200]}"
        )

    print_step("Logging in after registration")
    follow_up = client.post("/v1/auth/login", json=payload)
    if follow_up.status_code != 200:
        detail = follow_up.text[:1_200]
        raise RuntimeError(
            f"Login after registration failed with HTTP {follow_up.status_code}: {detail}"
        )
    print_note("Login after registration succeeded")


def create_api_key_http(
    client: httpx.Client,
    *,
    name: str,
    scope: Mapping[str, Any],
) -> TemporaryApiKey:
    payload = {"name": name, "scope": dict(scope)}
    data = request_json(
        client,
        "POST",
        "/v1/auth/api-keys",
        label=f"Create API key '{name}'",
        expected_statuses=201,
        json=payload,
    )
    return TemporaryApiKey(id=data["id"], key=data["key"], label=name)


def delete_api_key_http(client: httpx.Client, api_key_id: str) -> None:
    request_json(
        client,
        "DELETE",
        f"/v1/auth/api-keys/{api_key_id}",
        label=f"Delete API key '{api_key_id}'",
        expected_statuses=(204, 404),
        quiet=True,
    )


def delete_sandbox_http(client: httpx.Client, sandbox_id: str) -> None:
    request_json(
        client,
        "DELETE",
        f"/v1/sandboxes/{sandbox_id}",
        label=f"Delete sandbox '{sandbox_id}'",
        expected_statuses=(204, 404),
        quiet=True,
    )


def wait_for_sandbox_ready(
    fetch_detail: Callable[[], Any],
    *,
    timeout_seconds: float = 600.0,
    poll_interval_seconds: float = 5.0,
) -> Any:
    started_at = time.monotonic()
    while True:
        detail = fetch_detail()
        status = get_value(detail, "status")
        sandbox_id = get_value(detail, "id")
        message = get_value(detail, "status_message")

        print_note(f"Sandbox {sandbox_id}: status={status!r} message={message!r}")

        if status == READY_STATUS:
            return detail
        if status in FAILED_STATUSES:
            raise RuntimeError(f"Sandbox {sandbox_id} entered terminal status '{status}': {message}")
        if time.monotonic() - started_at > timeout_seconds:
            raise RuntimeError(f"Timed out waiting for sandbox {sandbox_id} to become ready.")

        time.sleep(poll_interval_seconds)


def best_effort(label: str, fn: Callable[[], None]) -> None:
    try:
        fn()
        print_note(f"{label}: done")
    except Exception as exc:  # pragma: no cover - best effort cleanup path
        print_note(f"{label}: skipped ({exc})")


def control_plane_none_scope() -> dict[str, Any]:
    return {
        "control_plane": True,
        "data_plane": {
            "mode": "none",
            "sandbox_ids": [],
        },
    }


def selected_data_plane_scope(sandbox_id: str) -> dict[str, Any]:
    return {
        "control_plane": False,
        "data_plane": {
            "mode": "selected",
            "sandbox_ids": [sandbox_id],
        },
    }


def unwrap_data_plane_response(response: Mapping[str, Any], *, label: str) -> Any:
    if not response.get("success", False):
        message = response.get("message", "Unknown error")
        raise RuntimeError(f"{label} failed: {message}")
    return response.get("data")


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1
