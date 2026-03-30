"""Sandbox template commands."""

from __future__ import annotations

import click

from treadstone_cli._client import require_auth
from treadstone_cli._output import handle_error, is_json_mode, print_json, print_table


@click.group(invoke_without_command=True)
@click.pass_context
def templates(ctx: click.Context) -> None:
    """Manage sandbox templates.

    Templates define the runtime environment (image, CPU, memory) for sandboxes.
    List templates before creating a sandbox when you need a valid template name.
    Running `treadstone templates` with no subcommand is the same as
    `treadstone templates list`.

    \b
    Examples:
      treadstone templates list
      treadstone templates
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_templates)


@templates.command("list", short_help="List sandbox templates and resource specs.")
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """List all available sandbox templates with resource specs."""
    client = require_auth(ctx)
    resp = client.get("/v1/sandbox-templates")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        items = data.get("items", [])
        rows = [
            [t["name"], t["display_name"], t["resource_spec"]["cpu"], t["resource_spec"]["memory"], t["description"]]
            for t in items
        ]
        print_table(["Name", "Display Name", "CPU", "Memory", "Description"], rows, title="Sandbox Templates")
