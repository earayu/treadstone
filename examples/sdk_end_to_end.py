from __future__ import annotations

from typing import Any, TypeVar

from _shared import (
    TemporaryApiKey,
    best_effort,
    build_sdk_data_plane_base,
    control_plane_none_scope,
    create_api_key_http,
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
    wait_for_sandbox_ready,
)

T = TypeVar("T")


def expect_instance(value: Any, expected_type: type[T], label: str) -> T:  # noqa: UP047
    if not isinstance(value, expected_type):
        actual = type(value).__name__ if value is not None else "None"
        raise RuntimeError(f"{label} returned {actual}, expected {expected_type.__name__}.")
    return value


def main() -> int:
    config = parse_common_args(
        description="End-to-end Treadstone example using treadstone-sdk and agent-sandbox.",
        name_prefix="sdk-example",
    )

    try:
        from agent_sandbox import Sandbox as DataPlaneSandbox
        from treadstone_sdk import AuthenticatedClient, Client
        from treadstone_sdk.api.auth import auth_create_api_key, auth_delete_api_key
        from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
        from treadstone_sdk.api.sandboxes import (
            sandboxes_create_sandbox,
            sandboxes_delete_sandbox,
            sandboxes_get_sandbox,
        )
        from treadstone_sdk.api.system import system_health
        from treadstone_sdk.models.api_key_data_plane_mode import ApiKeyDataPlaneMode
        from treadstone_sdk.models.api_key_data_plane_scope import ApiKeyDataPlaneScope
        from treadstone_sdk.models.api_key_response import ApiKeyResponse
        from treadstone_sdk.models.api_key_scope import ApiKeyScope
        from treadstone_sdk.models.create_api_key_request import CreateApiKeyRequest
        from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
        from treadstone_sdk.models.sandbox_detail_response import SandboxDetailResponse
        from treadstone_sdk.models.sandbox_response import SandboxResponse
        from treadstone_sdk.models.sandbox_template_list_response import SandboxTemplateListResponse
    except ImportError:
        return fail(
            "Missing dependencies. Run:\n"
            "uv run --with httpx --with treadstone-sdk --with agent-sandbox python examples/sdk_end_to_end.py"
        )

    print_header("SDK End-to-End Example")

    temporary_keys: list[TemporaryApiKey] = []
    sandbox_id: str | None = None

    try:
        public_client = Client(base_url=config.base_url, follow_redirects=True)
        health = system_health.sync(client=public_client)
        if health is None:
            raise RuntimeError("Health check returned no payload.")
        print_json("Health response", health)

        bootstrap_key = config.api_key
        if bootstrap_key:
            print_step("Using TREADSTONE_API_KEY as the bootstrap control-plane credential")
        else:
            session_client = new_http_client(config.base_url)
            login_or_register(session_client, config)
            bootstrap = create_api_key_http(
                session_client,
                name="examples-sdk-bootstrap",
                scope=control_plane_none_scope(),
            )
            temporary_keys.append(bootstrap)
            bootstrap_key = bootstrap.key
            print_json("Bootstrap API key metadata", {"id": bootstrap.id, "label": bootstrap.label})
            session_client.close()

        if bootstrap_key is None:
            raise RuntimeError("Failed to resolve a bootstrap API key.")

        control_client = AuthenticatedClient(
            base_url=config.base_url,
            token=bootstrap_key,
            follow_redirects=True,
        )

        templates = expect_instance(
            sandbox_templates_list_sandbox_templates.sync(client=control_client),
            SandboxTemplateListResponse,
            "List sandbox templates",
        )
        ensure_template_exists(templates, config.template)
        print_json("Available templates", templates)

        sandbox_name = make_sandbox_name(config.name_prefix)
        created = expect_instance(
            sandboxes_create_sandbox.sync(
                client=control_client,
                body=CreateSandboxRequest(template=config.template, name=sandbox_name),
            ),
            SandboxResponse,
            "Create sandbox",
        )
        sandbox_id = created.id
        print_json("Sandbox create response", created)

        sandbox_detail = wait_for_sandbox_ready(
            lambda: expect_instance(
                sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=control_client),
                SandboxDetailResponse,
                f"Get sandbox {sandbox_id}",
            )
        )
        print_json("Sandbox detail", sandbox_detail)

        data_plane_scope = ApiKeyScope(
            control_plane=False,
            data_plane=ApiKeyDataPlaneScope(
                mode=ApiKeyDataPlaneMode.SELECTED,
                sandbox_ids=[sandbox_id],
            ),
        )
        data_plane_key = expect_instance(
            auth_create_api_key.sync(
                client=control_client,
                body=CreateApiKeyRequest(
                    name=f"{sandbox_name}-data-plane",
                    scope=data_plane_scope,
                ),
            ),
            ApiKeyResponse,
            "Create sandbox-scoped data-plane key",
        )
        temporary_keys.append(
            TemporaryApiKey(
                id=data_plane_key.id,
                key=data_plane_key.key,
                label=f"{sandbox_name}-data-plane",
            )
        )
        print_json(
            "Data-plane API key metadata",
            {"id": data_plane_key.id, "label": f"{sandbox_name}-data-plane"},
        )

        proxy_url = get_value(sandbox_detail, "urls", "proxy")
        data_plane_client = DataPlaneSandbox(
            base_url=build_sdk_data_plane_base(proxy_url),
            headers={"Authorization": f"Bearer {data_plane_key.key}"},
        )

        sandbox_context = data_plane_client.sandbox.get_context()
        print_json("Data-plane sandbox context", sandbox_context)

        file_path = f"/tmp/{sandbox_name}-sdk.txt"
        marker = f"marker:{sandbox_name}"

        shell_result = data_plane_client.shell.exec_command(
            command=f"printf '{marker}' > {file_path} && cat {file_path}"
        )
        print_json("Shell exec result", shell_result)

        file_write = data_plane_client.file.write_file(file=file_path, content=marker)
        print_json("File write result", file_write)

        file_read = data_plane_client.file.read_file(file=file_path)
        print_json("File read result", file_read)

        browser_info = data_plane_client.browser.get_info()
        print_json("Browser info", browser_info)

        return 0
    except Exception as exc:
        return fail(f"SDK example failed: {exc}")
    finally:
        if "control_client" in locals():
            if sandbox_id and not config.keep_sandbox:
                best_effort(
                    f"Delete sandbox {sandbox_id}",
                    lambda: sandboxes_delete_sandbox.sync(sandbox_id=sandbox_id, client=control_client),
                )
            elif sandbox_id:
                print_step(f"Keeping sandbox {sandbox_id} because --keep-sandbox was set")

            if not config.keep_keys:
                for api_key in reversed(temporary_keys):
                    best_effort(
                        f"Delete API key {api_key.id}",
                        lambda key_id=api_key.id: auth_delete_api_key.sync(key_id=key_id, client=control_client),
                    )
            elif temporary_keys:
                print_step("Keeping temporary API keys because --keep-keys was set")


if __name__ == "__main__":
    raise SystemExit(main())
