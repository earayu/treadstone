"""Local CLI configuration commands.

Manages ~/.config/treadstone/config.toml which stores defaults for
base_url, api_key, and other settings so they don't need to be passed
as flags or env vars every time.
"""

from __future__ import annotations

import click

import treadstone_cli._client as client_state

_VALID_KEYS = ("base_url", "api_key")


@click.group()
def config() -> None:
    """Manage local CLI configuration.

    Configuration is stored in ~/.config/treadstone/config.toml and provides
    default values for --base-url and --api-key so they don't need to be
    repeated on every command invocation. Saved login sessions live in a
    separate local state file and are not managed by this command group.

    \b
    Priority (highest to lowest):
      1. CLI flags   (--base-url, --api-key)
      2. Env vars    (TREADSTONE_BASE_URL, TREADSTONE_API_KEY)
      3. Config file (~/.config/treadstone/config.toml)
    """


@config.command("set")
@click.argument("key", type=click.Choice(_VALID_KEYS, case_sensitive=False))
@click.argument("value")
def set_value(key: str, value: str) -> None:
    """Set a configuration value.

    \b
    Available keys:
      base_url   Base URL of the Treadstone server
      api_key    Default API key for authentication

    \b
    Examples:
      treadstone config set base_url https://my-server.example.com
      treadstone config set api_key ts_live_xxxxxxxxxxxx
    """
    client_state.set_config_value(key, value)
    click.echo(f"Set {key} = {value}")


@config.command("get")
@click.argument("key", required=False, default=None)
def get_value(key: str | None) -> None:
    """Get a configuration value (or all values if no key given).

    \b
    Examples:
      treadstone config get              Show all config values
      treadstone config get base_url     Show only base_url
    """
    data = client_state._read_config()
    if not data:
        click.echo("No configuration set. Run 'treadstone config set <key> <value>' to get started.")
        return

    if key is not None:
        if key not in _VALID_KEYS:
            click.echo(f"Error: Unknown key '{key}'. Valid keys: {', '.join(_VALID_KEYS)}", err=True)
            raise SystemExit(1)
        val = data.get(key)
        if val is None:
            click.echo(f"{key} is not set.")
        else:
            display = _mask_secret(key, val)
            click.echo(f"{key} = {display}")
    else:
        for k in _VALID_KEYS:
            val = data.get(k)
            if val is not None:
                click.echo(f"{k} = {_mask_secret(k, val)}")


@config.command("unset")
@click.argument("key", type=click.Choice(_VALID_KEYS, case_sensitive=False))
def unset_value(key: str) -> None:
    """Remove a configuration value.

    \b
    Example:
      treadstone config unset api_key
    """
    if client_state.unset_config_value(key):
        click.echo(f"Unset {key}.")
    else:
        click.echo(f"{key} is not set.")


@config.command("path")
def show_path() -> None:
    """Print the path to the configuration file.

    \b
    Example:
      treadstone config path
    """
    exists = client_state.CONFIG_FILE.exists()
    click.echo(str(client_state.CONFIG_FILE))
    if not exists:
        click.echo("  (file does not exist yet)")


def _mask_secret(key: str, value: str) -> str:
    if key == "api_key" and len(value) > 8:
        return value[:8] + "..." + value[-4:]
    return value
