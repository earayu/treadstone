"""Output formatting utilities for CLI — table (Rich) or JSON mode."""

from __future__ import annotations

import json
import sys
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()


def friendly_exception_handler(cli_main: click.Group) -> click.Group:
    """Wrap a Click group so unhandled exceptions print user-friendly messages instead of tracebacks."""
    original_main = cli_main.main

    def _patched_main(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_main(*args, standalone_mode=False, **kwargs)
        except click.exceptions.Abort:
            click.echo("\nAborted.", err=True)
            sys.exit(130)
        except click.exceptions.Exit as exc:
            sys.exit(exc.exit_code)
        except click.UsageError as exc:
            exc.show()
            sys.exit(exc.exit_code if exc.exit_code is not None else 2)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            click.echo("\nInterrupted.", err=True)
            sys.exit(130)
        except httpx.ConnectError as exc:
            _print_network_hint(str(exc), "Connection refused")
            sys.exit(1)
        except httpx.TimeoutException:
            click.echo("Error: Request timed out. The server may be slow or unreachable.", err=True)
            sys.exit(1)
        except httpx.HTTPStatusError as exc:
            click.echo(f"Error: HTTP {exc.response.status_code} — {exc.response.text[:200]}", err=True)
            sys.exit(1)
        except httpx.HTTPError as exc:
            click.echo(f"Error: {type(exc).__name__} — {exc}", err=True)
            sys.exit(1)
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    cli_main.main = _patched_main  # type: ignore[assignment]
    return cli_main


def _print_network_hint(detail: str, summary: str) -> None:
    click.echo(f"Error: {summary}.", err=True)
    click.echo("  Possible causes:", err=True)
    click.echo("    - The Treadstone server is not running", err=True)
    click.echo("    - The --base-url or TREADSTONE_BASE_URL is incorrect", err=True)
    click.echo("    - A firewall or proxy is blocking the connection", err=True)
    click.echo(f"  Detail: {detail}", err=True)


def is_json_mode(ctx: click.Context) -> bool:
    return ctx.obj.get("json_output", False)


def print_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def print_table(columns: list[str], rows: list[list[Any]], title: str | None = None) -> None:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(v) if v is not None else "" for v in row])
    console.print(table)


def print_detail(data: dict[str, Any], title: str | None = None) -> None:
    table = Table(title=title, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for k, v in data.items():
        table.add_row(k, str(v) if v is not None else "")
    console.print(table)


def handle_error(resp: Any) -> None:
    """Print error and exit if response is not 2xx."""
    if resp.status_code >= 400:
        try:
            body = resp.json()
            err = body.get("error", body)
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        except Exception:
            msg = resp.text
        click.echo(f"Error ({resp.status_code}): {msg}", err=True)
        sys.exit(1)
