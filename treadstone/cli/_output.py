"""Output formatting utilities for CLI — table (Rich) or JSON mode."""

from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()


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
