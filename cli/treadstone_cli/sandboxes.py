"""Sandbox management commands."""

from __future__ import annotations

import click

from treadstone_cli._client import require_auth
from treadstone_cli._output import handle_error, is_json_mode, print_detail, print_json, print_table


@click.group()
def sandboxes() -> None:
    """Manage sandboxes.

    Create, list, start, stop, and delete sandboxes. Use 'sb' as a shorthand.

    \b
    Examples:
      treadstone sandboxes create --template default --name my-box
      treadstone sb list
      treadstone sb get <sandbox-id>
      treadstone sb delete <sandbox-id>
    """


@sandboxes.command("create")
@click.option("--template", required=True, help="Sandbox template name.")
@click.option(
    "--name",
    default=None,
    help=(
        "Sandbox name (auto-generated if omitted). Must be 1-55 characters of lowercase letters, "
        "numbers, or hyphens; must start and end with a letter or number. "
        "This keeps sandbox-{name} within DNS label limits."
    ),
)
@click.option("--label", multiple=True, help="Labels in key:val format (repeatable).")
@click.option("--persist", is_flag=True, default=False, help="Enable persistent storage.")
@click.option("--storage-size", default="10Gi", help="PVC size when --persist is set.")
@click.pass_context
def create(
    ctx: click.Context,
    template: str,
    name: str | None,
    label: tuple[str, ...],
    persist: bool,
    storage_size: str,
) -> None:
    """Create a new sandbox from a template.

    Custom names must be 1-55 characters of lowercase letters, numbers, or
    hyphens, and must start and end with a letter or number. This keeps
    browser URLs like sandbox-{name}.treadstone-ai.dev within DNS label limits.

    \b
    Examples:
      treadstone sb create --template default
      treadstone sb create --template python --name dev-box --label env:dev
      treadstone sb create --template node --persist --storage-size 20Gi
    """
    client = require_auth(ctx)
    labels = {}
    for lbl in label:
        if ":" not in lbl:
            click.echo(f"Error: Invalid label format '{lbl}'. Use key:val.", err=True)
            raise SystemExit(1)
        k, v = lbl.split(":", 1)
        labels[k] = v
    body: dict = {"template": template, "labels": labels, "persist": persist, "storage_size": storage_size}
    if name:
        body["name"] = name
    resp = client.post("/v1/sandboxes", json=body)
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title="Sandbox Created")


@sandboxes.command("list")
@click.option("--label", default=None, help="Filter by label (key:val).")
@click.option("--limit", default=100, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Skip N results.")
@click.pass_context
def list_sandboxes(ctx: click.Context, label: str | None, limit: int, offset: int) -> None:
    """List sandboxes with optional filtering.

    \b
    Examples:
      treadstone sb list
      treadstone sb list --label env:prod --limit 10
    """
    client = require_auth(ctx)
    params: dict = {"limit": limit, "offset": offset}
    if label:
        params["label"] = label
    resp = client.get("/v1/sandboxes", params=params)
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        items = data.get("items", [])
        rows = [[s["id"], s["name"], s["template"], s["status"], s.get("created_at", "")] for s in items]
        print_table(["ID", "Name", "Template", "Status", "Created"], rows, title=f"Sandboxes ({data['total']} total)")


@sandboxes.command("get")
@click.argument("sandbox_id")
@click.pass_context
def get_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Show detailed information about a sandbox."""
    client = require_auth(ctx)
    resp = client.get(f"/v1/sandboxes/{sandbox_id}")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title=f"Sandbox {sandbox_id}")


@sandboxes.command("delete")
@click.argument("sandbox_id")
@click.pass_context
def delete_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Delete a sandbox."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/sandboxes/{sandbox_id}")
    handle_error(resp)
    click.echo(f"Sandbox {sandbox_id} deleted.")


@sandboxes.command("start")
@click.argument("sandbox_id")
@click.pass_context
def start_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Start a stopped sandbox."""
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/start")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Sandbox {sandbox_id} starting.")


@sandboxes.command("stop")
@click.argument("sandbox_id")
@click.pass_context
def stop_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Stop a running sandbox."""
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/stop")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Sandbox {sandbox_id} stopping.")


@sandboxes.command("token")
@click.argument("sandbox_id")
@click.option("--expires-in", default=3600, type=int, help="Token lifetime in seconds.")
@click.pass_context
def create_token(ctx: click.Context, sandbox_id: str, expires_in: int) -> None:
    """Create a short-lived access token for a sandbox.

    The token can be used to connect to the sandbox directly (e.g. via
    WebSocket) without needing the main API key.
    """
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": expires_in})
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title="Sandbox Token")
