"""Treadstone CLI — agent-native sandbox management."""

from __future__ import annotations

import click

from treadstone.cli._client import build_client
from treadstone.cli._output import friendly_exception_handler, handle_error, is_json_mode, print_json

_EPILOG = """\b
Configuration (highest to lowest priority):
  CLI flags       --api-key, --base-url
  Env vars        TREADSTONE_API_KEY, TREADSTONE_BASE_URL
  Config file     ~/.config/treadstone/config.toml

  Run 'treadstone config --help' to manage the config file.

Examples:
  treadstone health                         Check server status
  treadstone sandboxes list                 List running sandboxes
  treadstone sb create --template default   Create a sandbox
  treadstone auth login                     Log in with email/password
"""


@click.group(epilog=_EPILOG)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output in JSON format.")
@click.option(
    "--api-key",
    envvar="TREADSTONE_API_KEY",
    default=None,
    help="API key for authentication (env: TREADSTONE_API_KEY).",
)
@click.option(
    "--base-url",
    envvar="TREADSTONE_BASE_URL",
    default=None,
    help="Base URL of the Treadstone server (env: TREADSTONE_BASE_URL).",
)
@click.version_option(package_name="treadstone")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, api_key: str | None, base_url: str | None) -> None:
    """Treadstone CLI — manage sandboxes, templates, and API keys.

    An agent-native sandbox service. Run code, build projects, and deploy
    environments via the command line.
    """
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    if api_key:
        ctx.obj["api_key"] = api_key
    if base_url:
        ctx.obj["base_url"] = base_url


@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check if the Treadstone server is reachable and healthy."""
    client = build_client(ctx)
    resp = client.get("/health")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        status = data.get("status", "unknown")
        click.echo(f"Server is {status}")


from treadstone.cli.api_keys import api_keys  # noqa: E402
from treadstone.cli.auth import auth  # noqa: E402
from treadstone.cli.config_cmd import config  # noqa: E402
from treadstone.cli.sandboxes import sandboxes  # noqa: E402
from treadstone.cli.templates import templates  # noqa: E402

cli.add_command(auth)
cli.add_command(api_keys, "api-keys")
cli.add_command(sandboxes)
cli.add_command(sandboxes, "sb")
cli.add_command(templates)
cli.add_command(config)

friendly_exception_handler(cli)
