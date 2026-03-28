"""API key management commands."""

from __future__ import annotations

import click
from click.core import ParameterSource

from treadstone_cli._client import CONFIG_FILE, require_auth, set_config_value
from treadstone_cli._output import handle_error, is_json_mode, print_json, print_table


@click.group()
def api_keys() -> None:
    """Manage API keys.

    API keys provide long-lived authentication tokens for programmatic access.
    Use them when you need a reusable non-interactive credential instead of a
    saved login session.

    \b
    Examples:
      treadstone api-keys create --name ci-bot
      treadstone api-keys create --name agent --save
      treadstone api-keys create --no-control-plane --data-plane selected --sandbox-id sb123
      treadstone api-keys list
      treadstone api-keys update <key-id> --data-plane none
      treadstone api-keys delete <key-id>
    """


def _build_scope(control_plane: bool | None, data_plane: str | None, sandbox_ids: tuple[str, ...]) -> dict | None:
    if control_plane is None and data_plane is None and not sandbox_ids:
        return None

    mode = data_plane or "all"
    sandbox_id_list = list(dict.fromkeys(sandbox_ids))
    if mode == "selected" and not sandbox_id_list:
        click.echo("Error: --sandbox-id is required when --data-plane selected.", err=True)
        raise SystemExit(1)
    if mode != "selected" and sandbox_id_list:
        click.echo("Error: --sandbox-id is only allowed when --data-plane selected.", err=True)
        raise SystemExit(1)

    return {
        "control_plane": True if control_plane is None else control_plane,
        "data_plane": {"mode": mode, "sandbox_ids": sandbox_id_list},
    }


@api_keys.command("create")
@click.option("--name", default="default", show_default=True, help="Key name.")
@click.option("--expires-in", default=None, type=int, help="Key lifetime in seconds.")
@click.option("--control-plane/--no-control-plane", default=None, help="Enable or disable control plane access.")
@click.option(
    "--data-plane",
    type=click.Choice(["none", "all", "selected"]),
    default=None,
    help="Configure data plane access.",
)
@click.option("--sandbox-id", "sandbox_ids", multiple=True, help="Allowlist sandbox ID when --data-plane selected.")
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save the new key as the default api_key in local CLI config.",
)
@click.pass_context
def create_key(
    ctx: click.Context,
    name: str,
    expires_in: int | None,
    control_plane: bool | None,
    data_plane: str | None,
    sandbox_ids: tuple[str, ...],
    save: bool,
) -> None:
    """Create a new API key.

    The full key is shown only once. Use --save to store it as the default
    local api_key for future commands.
    """
    client = require_auth(ctx)
    body: dict = {"name": name}
    if expires_in is not None:
        body["expires_in"] = expires_in
    scope = _build_scope(control_plane, data_plane, sandbox_ids)
    if scope is not None:
        body["scope"] = scope
    resp = client.post("/v1/auth/api-keys", json=body)
    handle_error(resp)
    data = resp.json()
    if save:
        set_config_value("api_key", data["key"])
    if is_json_mode(ctx):
        print_json({**data, "saved_to_config": save, "config_file": str(CONFIG_FILE) if save else None})
    else:
        click.echo(f"API Key created: {data['key']}")
        click.echo(f"  ID: {data['id']}  Name: {data['name']}")
        click.echo("  Store this key securely — it won't be shown again.")
        if save:
            click.echo(f"  Saved as the default api_key in {CONFIG_FILE}.")


@api_keys.command("list")
@click.pass_context
def list_keys(ctx: click.Context) -> None:
    """List all API keys for the current user."""
    client = require_auth(ctx)
    resp = client.get("/v1/auth/api-keys")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        items = data.get("items", [])
        rows = [
            [
                k["id"],
                k["name"],
                k["key_prefix"],
                "yes" if k["scope"]["control_plane"] else "no",
                k["scope"]["data_plane"]["mode"],
                ",".join(k["scope"]["data_plane"]["sandbox_ids"]),
                k.get("expires_at", ""),
            ]
            for k in items
        ]
        print_table(
            ["ID", "Name", "Key Prefix", "Control", "Data", "Sandboxes", "Expires"],
            rows,
            title="API Keys",
        )


@api_keys.command("update")
@click.argument("key_id")
@click.option("--name", default=None, help="New key name.")
@click.option("--expires-in", default=None, type=int, help="Reset expiration from now in seconds.")
@click.option("--clear-expiration", is_flag=True, default=False, help="Make the key non-expiring.")
@click.option("--control-plane/--no-control-plane", default=None, help="Enable or disable control plane access.")
@click.option(
    "--data-plane",
    type=click.Choice(["none", "all", "selected"]),
    default=None,
    help="Configure data plane access.",
)
@click.option("--sandbox-id", "sandbox_ids", multiple=True, help="Allowlist sandbox ID when --data-plane selected.")
@click.pass_context
def update_key(
    ctx: click.Context,
    key_id: str,
    name: str | None,
    expires_in: int | None,
    clear_expiration: bool,
    control_plane: bool | None,
    data_plane: str | None,
    sandbox_ids: tuple[str, ...],
) -> None:
    """Update an API key in place."""
    client = require_auth(ctx)
    body: dict = {}
    if name is not None:
        body["name"] = name
    if expires_in is not None:
        body["expires_in"] = expires_in
    if clear_expiration:
        body["clear_expiration"] = True

    if (
        ctx.get_parameter_source("control_plane") != ParameterSource.DEFAULT
        or ctx.get_parameter_source("data_plane") != ParameterSource.DEFAULT
        or sandbox_ids
    ):
        body["scope"] = _build_scope(control_plane, data_plane, sandbox_ids)

    if not body:
        click.echo("Error: No updates specified.", err=True)
        raise SystemExit(1)

    resp = client.patch(f"/v1/auth/api-keys/{key_id}", json=body)
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"API key {key_id} updated.")
        click.echo(
            f"  Name: {data['name']}  Control: {'yes' if data['scope']['control_plane'] else 'no'}"
            f"  Data: {data['scope']['data_plane']['mode']}"
        )


@api_keys.command("delete")
@click.argument("key_id")
@click.pass_context
def delete_key(ctx: click.Context, key_id: str) -> None:
    """Revoke and delete an API key."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/auth/api-keys/{key_id}")
    handle_error(resp)
    click.echo(f"API key {key_id} deleted.")
