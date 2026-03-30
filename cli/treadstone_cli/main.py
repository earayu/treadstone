"""Treadstone CLI entrypoint."""

from __future__ import annotations

import click

from treadstone_cli._client import effective_api_key, effective_base_url, effective_default_template, effective_session
from treadstone_cli._output import friendly_exception_handler


def _active_base_url(ctx: click.Context) -> tuple[str, str]:
    base_url = ctx.params.get("base_url")
    if base_url:
        return base_url.rstrip("/"), "flag"
    return effective_base_url()


def _active_api_key_status(ctx: click.Context) -> str:
    if ctx.params.get("api_key"):
        return "configured [flag]"
    if effective_api_key():
        return "configured"
    return "not set"


def _active_auth_mode(api_key_present: bool, session_present: bool) -> str:
    if api_key_present and session_present:
        return "API key (takes precedence over saved session)"
    if api_key_present:
        return "API key"
    if session_present:
        return "saved session"
    return "none"


def _leaf_command_rows(group: click.Group, ctx: click.Context, prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for name in group.list_commands(ctx):
        if not prefix and name == "sb":
            continue
        command = group.get_command(ctx, name)
        if command is None:
            continue
        path = f"{prefix} {name}".strip()
        if isinstance(command, click.Group):
            rows.extend(_leaf_command_rows(command, ctx, path))
        else:
            rows.append((path, command.get_short_help_str()))
    return rows


class _TreadstoneGroup(click.Group):
    """Custom root group with richer help sections."""

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        base_url, source = _active_base_url(ctx)
        default_template, template_source = effective_default_template()
        api_key_present = _active_api_key_status(ctx) != "not set"
        session_present = effective_session(base_url)

        with formatter.section("Authentication"):
            formatter.write_text(
                "Protected commands prefer an API key (flag, env, or saved config); "
                "they fall back to the saved login session when no key is present. "
                "Use 'treadstone auth login' for interactive sessions and "
                "'treadstone api-keys create --save' for non-interactive automation."
            )

        with formatter.section("Command Reference"):
            formatter.write_dl(_leaf_command_rows(self, ctx))

        with formatter.section("Quick Start"):
            formatter.write_dl(
                [
                    ("Check connectivity", "treadstone system health"),
                    ("Sign in interactively", "treadstone auth login"),
                    ("List templates (JSON)", "treadstone --json templates list"),
                    ("Create a sandbox (JSON)", "treadstone --json sandboxes create --name demo"),
                    ("Get a browser hand-off URL", "treadstone --json sandboxes web enable SANDBOX_ID"),
                    ("Print the agent skill", "treadstone skills"),
                    ("Install the agent skill", "treadstone skills install"),
                ]
            )

        with formatter.section("Active Configuration"):
            formatter.write_dl(
                [
                    ("Base URL", f"{base_url}  [{source}]"),
                    ("Default sandbox template", f"{default_template}  [{template_source}]"),
                    ("API key", _active_api_key_status(ctx)),
                    ("Saved session", "available" if session_present else "not set"),
                    ("Auth used by protected commands", _active_auth_mode(api_key_present, session_present)),
                ]
            )


@click.group(cls=_TreadstoneGroup)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output command results in JSON format.")
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
@click.version_option(package_name="treadstone-cli")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, api_key: str | None, base_url: str | None) -> None:
    """Manage Treadstone sandboxes, auth, API keys, and configuration."""
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    if api_key:
        ctx.obj["api_key"] = api_key
    if base_url:
        ctx.obj["base_url"] = base_url


from treadstone_cli.api_keys import api_keys  # noqa: E402
from treadstone_cli.auth import auth  # noqa: E402
from treadstone_cli.config_cmd import config  # noqa: E402
from treadstone_cli.sandboxes import sandboxes  # noqa: E402
from treadstone_cli.skills_cmd import skills  # noqa: E402
from treadstone_cli.system import system  # noqa: E402
from treadstone_cli.templates import templates  # noqa: E402

cli.add_command(system)
cli.add_command(auth)
cli.add_command(api_keys, "api-keys")
cli.add_command(sandboxes)
cli.add_command(sandboxes, "sb")
cli.add_command(templates)
cli.add_command(config)
cli.add_command(skills)

friendly_exception_handler(cli)
