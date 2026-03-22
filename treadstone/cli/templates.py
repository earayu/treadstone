"""Sandbox template commands."""

from __future__ import annotations

import click

from treadstone.cli._client import require_auth
from treadstone.cli._output import handle_error, is_json_mode, print_json, print_table


@click.group()
def templates() -> None:
    """Manage sandbox templates."""


@templates.command("list")
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """List available sandbox templates."""
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
