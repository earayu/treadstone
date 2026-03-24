"""Guide commands for humans and agents."""

from __future__ import annotations

import click

from treadstone_cli._guide_text import AGENT_GUIDE


@click.group()
def guide() -> None:
    """Usage guides for humans and agents.

    \b
    Examples:
      treadstone guide agent
      treadstone --skills
    """


@guide.command("agent")
def agent_guide() -> None:
    """Print the agent-oriented usage guide."""
    click.echo(AGENT_GUIDE.rstrip())
