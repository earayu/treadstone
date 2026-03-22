"""API key management commands."""

from __future__ import annotations

import click

from treadstone.cli._client import require_auth
from treadstone.cli._output import handle_error, is_json_mode, print_json, print_table


@click.group()
def api_keys() -> None:
    """Manage API keys."""


@api_keys.command("create")
@click.option("--name", default="default", help="Key name.")
@click.option("--expires-in", default=None, type=int, help="Key lifetime in seconds.")
@click.pass_context
def create_key(ctx: click.Context, name: str, expires_in: int | None) -> None:
    """Create a new API key."""
    client = require_auth(ctx)
    body: dict = {"name": name}
    if expires_in is not None:
        body["expires_in"] = expires_in
    resp = client.post("/v1/auth/api-keys", json=body)
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"API Key created: {data['key']}")
        click.echo(f"  ID: {data['id']}  Name: {data['name']}")
        click.echo("  Store this key securely — it won't be shown again.")


@api_keys.command("list")
@click.pass_context
def list_keys(ctx: click.Context) -> None:
    """List API keys."""
    client = require_auth(ctx)
    resp = client.get("/v1/auth/api-keys")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        items = data.get("items", [])
        rows = [[k["id"], k["name"], k["key_prefix"], k.get("created_at", ""), k.get("expires_at", "")] for k in items]
        print_table(["ID", "Name", "Key Prefix", "Created", "Expires"], rows, title="API Keys")


@api_keys.command("delete")
@click.argument("key_id")
@click.pass_context
def delete_key(ctx: click.Context, key_id: str) -> None:
    """Delete an API key."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/auth/api-keys/{key_id}")
    handle_error(resp)
    click.echo(f"API key {key_id} deleted.")
