"""Config commands."""

from __future__ import annotations

import click

from treadstone.cli._client import build_client
from treadstone.cli._output import handle_error, is_json_mode, print_detail, print_json


@click.group()
def config() -> None:
    """Server configuration."""


@config.command("show")
@click.pass_context
def show(ctx: click.Context) -> None:
    """Show server configuration."""
    client = build_client(ctx)
    resp = client.get("/v1/config")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data.get("auth", data), title="Server Config")
