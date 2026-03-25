"""Sandbox management commands."""

from __future__ import annotations

import click

from treadstone_cli._client import require_auth
from treadstone_cli._output import handle_error, is_json_mode, print_detail, print_json, print_table

_STORAGE_SIZE_CHOICES = ("5Gi", "10Gi", "20Gi")


@click.group()
def sandboxes() -> None:
    """Manage sandboxes.

    Create, inspect, and control sandboxes. Use 'sb' as a shorthand.
    Sandbox names are human-readable labels; follow-up commands use sandbox IDs.

    \b
    Examples:
      treadstone --json sandboxes create --template aio-sandbox-tiny --name my-box
      treadstone --json sandboxes list --label env:dev
      treadstone sandboxes get sb-abc123def456
      treadstone sandboxes web enable sb-abc123def456
    """


@sandboxes.command("create")
@click.option("--template", required=True, help="Sandbox template name.")
@click.option(
    "--name",
    default=None,
    help=(
        "Sandbox name (auto-generated if omitted). Must be 1-55 characters of lowercase letters, "
        "numbers, or hyphens; must start and end with a letter or number. "
        "Sandbox names only need to be unique for the current user."
    ),
)
@click.option("--label", multiple=True, help="Labels in key:val format (repeatable).")
@click.option("--auto-stop-interval", default=15, type=int, help="Minutes of inactivity before the sandbox auto-stops.")
@click.option(
    "--auto-delete-interval",
    default=-1,
    type=int,
    help="Minutes after stop before auto-delete. Use -1 to disable auto-delete.",
)
@click.option("--persist", is_flag=True, default=False, help="Enable persistent storage.")
@click.option(
    "--storage-size",
    default="5Gi",
    type=click.Choice(_STORAGE_SIZE_CHOICES, case_sensitive=True),
    help="PVC size when --persist is set. Supported tiers: 5Gi, 10Gi, 20Gi.",
)
@click.pass_context
def create(
    ctx: click.Context,
    template: str,
    name: str | None,
    label: tuple[str, ...],
    auto_stop_interval: int,
    auto_delete_interval: int,
    persist: bool,
    storage_size: str,
) -> None:
    """Create a new sandbox from a template.

    Custom names must be 1-55 characters of lowercase letters, numbers, or
    hyphens, and must start and end with a letter or number. Sandbox names
    only need to be unique for the current user. Use `--json` if you need the
    returned `id`, `urls.proxy`, or `urls.web` for later automation steps.

    \b
    Examples:
      treadstone sandboxes create --template aio-sandbox-tiny
      treadstone sandboxes create --template aio-sandbox-medium --name dev-box --label env:dev
      treadstone sandboxes create --template aio-sandbox-large --persist --storage-size 5Gi
      treadstone sandboxes create --template aio-sandbox-small --auto-stop-interval 30 --auto-delete-interval 120
    """
    client = require_auth(ctx)
    labels = {}
    for lbl in label:
        if ":" not in lbl:
            click.echo(f"Error: Invalid label format '{lbl}'. Use key:val.", err=True)
            raise SystemExit(1)
        k, v = lbl.split(":", 1)
        labels[k] = v
    body: dict = {
        "template": template,
        "labels": labels,
        "auto_stop_interval": auto_stop_interval,
        "auto_delete_interval": auto_delete_interval,
        "persist": persist,
    }
    if persist:
        body["storage_size"] = storage_size
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
@click.option("--label", "labels", multiple=True, help="Filter by label (key:val). Repeat to require multiple labels.")
@click.option("--limit", default=100, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Skip N results.")
@click.pass_context
def list_sandboxes(ctx: click.Context, labels: tuple[str, ...], limit: int, offset: int) -> None:
    """List sandboxes with optional filtering.

    \b
    Examples:
      treadstone sandboxes list
      treadstone sandboxes list --label env:prod --limit 10
      treadstone sandboxes list --label env:dev --label team:agent
    """
    client = require_auth(ctx)
    params: dict = {"limit": limit, "offset": offset}
    if labels:
        params["label"] = list(labels)
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
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def get_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Show detailed information about a sandbox.

    SANDBOX_ID must be the sandbox ID, not the sandbox name. Obtain it from
    `treadstone sandboxes list` or the `id` field in create/get JSON output.
    """
    client = require_auth(ctx)
    resp = client.get(f"/v1/sandboxes/{sandbox_id}")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title=f"Sandbox {sandbox_id}")


@sandboxes.command("delete")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def delete_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Delete a sandbox by sandbox ID."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/sandboxes/{sandbox_id}")
    handle_error(resp)
    click.echo(f"Sandbox {sandbox_id} deleted.")


@sandboxes.command("start")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def start_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Start a stopped sandbox by sandbox ID."""
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/start")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Sandbox {sandbox_id} starting.")


@sandboxes.command("stop")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def stop_sandbox(ctx: click.Context, sandbox_id: str) -> None:
    """Stop a running sandbox by sandbox ID."""
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/stop")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Sandbox {sandbox_id} stopping.")


@sandboxes.group("web")
def web() -> None:
    """Manage browser hand-off URLs for a sandbox.

    Use SANDBOX_ID from `treadstone sandboxes list` or the `id` field in
    create/get JSON output. Sandbox names are not accepted here, and browser
    URLs are derived from sandbox IDs rather than sandbox names.

    \b
    Examples:
      treadstone sandboxes web enable sb-abc123def456
      treadstone sandboxes web status sb-abc123def456
      treadstone sandboxes web disable sb-abc123def456
    """


@web.command("enable")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def enable_web(ctx: click.Context, sandbox_id: str) -> None:
    """Ensure a browser hand-off URL exists for a sandbox."""
    client = require_auth(ctx)
    resp = client.post(f"/v1/sandboxes/{sandbox_id}/web-link")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title=f"Sandbox Web Access Enabled: {sandbox_id}")


@web.command("status")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def web_status(ctx: click.Context, sandbox_id: str) -> None:
    """Show browser hand-off URL status for a sandbox."""
    client = require_auth(ctx)
    resp = client.get(f"/v1/sandboxes/{sandbox_id}/web-link")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title=f"Sandbox Web Access: {sandbox_id}")


@web.command("disable")
@click.argument("sandbox_id", metavar="SANDBOX_ID")
@click.pass_context
def disable_web(ctx: click.Context, sandbox_id: str) -> None:
    """Disable the browser hand-off URL for a sandbox."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/sandboxes/{sandbox_id}/web-link")
    handle_error(resp)
    if is_json_mode(ctx):
        print_json({"detail": "Sandbox web access disabled.", "sandbox_id": sandbox_id})
    else:
        click.echo(f"Sandbox {sandbox_id} web access disabled.")
