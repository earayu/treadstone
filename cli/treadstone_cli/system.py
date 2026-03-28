"""System-level commands."""

from __future__ import annotations

import click

from treadstone_cli._client import build_client, get_base_url
from treadstone_cli._output import handle_error, is_json_mode, print_json


@click.group(invoke_without_command=True)
@click.pass_context
def system(ctx: click.Context) -> None:
    """Inspect server reachability and other platform-wide state.

    Running `treadstone system` with no subcommand is the same as
    `treadstone system health`.

    \b
    Examples:
      treadstone system health
      treadstone system
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(health)


@system.command("health")
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check if the Treadstone server is reachable and healthy."""
    client = build_client(ctx)
    base_url = get_base_url(ctx)
    if not is_json_mode(ctx):
        click.echo(f"Connecting to {base_url} ...")
    resp = client.get("/health")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        status = data.get("status", "unknown")
        click.echo(f"Server is {status}")
