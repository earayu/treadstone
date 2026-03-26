from __future__ import annotations

import httpx
from _shared import (
    ExampleConfig,
    TemporaryApiKey,
    best_effort,
    build_raw_data_plane_base,
    control_plane_none_scope,
    create_api_key_http,
    delete_api_key_http,
    delete_sandbox_http,
    ensure_template_exists,
    fail,
    get_value,
    login_or_register,
    make_sandbox_name,
    new_http_client,
    parse_common_args,
    print_header,
    print_json,
    print_step,
    request_json,
    selected_data_plane_scope,
    unwrap_data_plane_response,
    wait_for_sandbox_ready,
)


def create_control_plane_client(config: ExampleConfig) -> tuple[httpx.Client, str, list[TemporaryApiKey]]:
    session_client = new_http_client(config.base_url)
    temporary_keys: list[TemporaryApiKey] = []

    if config.api_key:
        print_step("Using TREADSTONE_API_KEY as the bootstrap control-plane credential")
        return new_http_client(config.base_url, api_key=config.api_key), config.api_key, temporary_keys

    login_or_register(session_client, config)

    bootstrap_key = create_api_key_http(
        session_client,
        name="examples-http-bootstrap",
        scope=control_plane_none_scope(),
    )
    temporary_keys.append(bootstrap_key)

    print_json("Bootstrap API key metadata", {"id": bootstrap_key.id, "label": bootstrap_key.label})
    return new_http_client(config.base_url, api_key=bootstrap_key.key), bootstrap_key.key, temporary_keys


def main() -> int:
    config = parse_common_args(
        description="End-to-end Treadstone example using raw HTTP for control plane and data plane.",
        name_prefix="http-example",
    )

    print_header("HTTP End-to-End Example")

    control_client: httpx.Client | None = None
    data_plane_client: httpx.Client | None = None
    sandbox_id: str | None = None
    temporary_keys: list[TemporaryApiKey] = []

    try:
        public_client = new_http_client(config.base_url)
        health = request_json(
            public_client,
            "GET",
            "/health",
            label="Health check",
            expected_statuses=200,
        )
        print_json("Health response", health)

        control_client, _, bootstrap_keys = create_control_plane_client(config)
        temporary_keys.extend(bootstrap_keys)

        templates = request_json(
            control_client,
            "GET",
            "/v1/sandbox-templates",
            label="List sandbox templates",
            expected_statuses=200,
        )
        ensure_template_exists(templates, config.template)
        print_json("Available templates", templates)

        sandbox_name = make_sandbox_name(config.name_prefix)
        sandbox = request_json(
            control_client,
            "POST",
            "/v1/sandboxes",
            label="Create sandbox",
            expected_statuses=202,
            json={"template": config.template, "name": sandbox_name},
        )
        sandbox_id = sandbox["id"]
        print_json("Sandbox create response", sandbox)

        sandbox_detail = wait_for_sandbox_ready(
            lambda: request_json(
                control_client,
                "GET",
                f"/v1/sandboxes/{sandbox_id}",
                label=f"Get sandbox {sandbox_id}",
                expected_statuses=200,
                quiet=True,
            )
        )
        print_json("Sandbox detail", sandbox_detail)

        data_plane_key = create_api_key_http(
            control_client,
            name=f"{sandbox_name}-data-plane",
            scope=selected_data_plane_scope(sandbox_id),
        )
        temporary_keys.append(data_plane_key)
        print_json("Data-plane API key metadata", {"id": data_plane_key.id, "label": data_plane_key.label})

        raw_data_plane_base = build_raw_data_plane_base(get_value(sandbox_detail, "urls", "proxy"))
        data_plane_client = httpx.Client(
            base_url=raw_data_plane_base,
            headers={"Authorization": f"Bearer {data_plane_key.key}"},
            timeout=30.0,
            follow_redirects=True,
        )

        sandbox_context = request_json(
            data_plane_client,
            "GET",
            "/sandbox",
            label="Data-plane sandbox context",
            expected_statuses=200,
        )
        print_json(
            "Data-plane sandbox context payload",
            unwrap_data_plane_response(sandbox_context, label="Data-plane sandbox context"),
        )

        file_path = f"/tmp/{sandbox_name}-http.txt"
        marker = f"marker:{sandbox_name}"

        shell_result = request_json(
            data_plane_client,
            "POST",
            "/shell/exec",
            label="Data-plane shell exec",
            expected_statuses=200,
            json={"command": f"printf '{marker}' > {file_path} && cat {file_path}"},
        )
        print_json("Shell exec payload", unwrap_data_plane_response(shell_result, label="Data-plane shell exec"))

        write_result = request_json(
            data_plane_client,
            "POST",
            "/file/write",
            label="Data-plane file write",
            expected_statuses=200,
            json={"file": file_path, "content": marker},
        )
        print_json("File write payload", unwrap_data_plane_response(write_result, label="Data-plane file write"))

        read_result = request_json(
            data_plane_client,
            "POST",
            "/file/read",
            label="Data-plane file read",
            expected_statuses=200,
            json={"file": file_path},
        )
        print_json("File read payload", unwrap_data_plane_response(read_result, label="Data-plane file read"))

        browser_info = request_json(
            data_plane_client,
            "GET",
            "/browser/info",
            label="Data-plane browser info",
            expected_statuses=200,
        )
        print_json("Browser info payload", unwrap_data_plane_response(browser_info, label="Data-plane browser info"))

        return 0
    except Exception as exc:
        return fail(f"HTTP example failed: {exc}")
    finally:
        if data_plane_client is not None:
            data_plane_client.close()

        if control_client is not None:
            if sandbox_id and not config.keep_sandbox:
                best_effort(
                    f"Delete sandbox {sandbox_id}",
                    lambda: delete_sandbox_http(control_client, sandbox_id),
                )
            elif sandbox_id:
                print_step(f"Keeping sandbox {sandbox_id} because --keep-sandbox was set")

            if not config.keep_keys:
                for api_key in reversed(temporary_keys):
                    best_effort(
                        f"Delete API key {api_key.id}",
                        lambda api_key_id=api_key.id: delete_api_key_http(control_client, api_key_id),
                    )
            elif temporary_keys:
                print_step("Keeping temporary API keys because --keep-keys was set")

            control_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
