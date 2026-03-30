"""Skills commands — print and install the built-in agent skill."""

from __future__ import annotations

import pathlib

import click

from treadstone_cli._guide_text import AGENT_GUIDE

_TARGETS: dict[str, pathlib.Path] = {
    "agents": pathlib.Path.home() / ".agents" / "skills",
    "cursor": pathlib.Path.home() / ".cursor" / "skills",
    "codex": pathlib.Path.home() / ".codex" / "skills",
    "project": pathlib.Path.cwd() / ".agents" / "skills",
}

_SKILL_DIR_NAME = "treadstone-cli"


@click.group(invoke_without_command=True)
@click.pass_context
def skills(ctx: click.Context) -> None:
    """Print or install the built-in agent skill.

    \b
    Examples:
      treadstone skills                          Print skill to stdout
      treadstone skills install                  Install to ~/.agents/skills/
      treadstone skills install --target cursor  Install to ~/.cursor/skills/
      treadstone skills install --target project Install to .agents/skills/ (cwd)
      treadstone skills install --dir /my/path   Install to /my/path/treadstone-cli/
    """
    if ctx.invoked_subcommand is None:
        click.echo(AGENT_GUIDE.rstrip())


@skills.command("install")
@click.option(
    "--target",
    type=click.Choice(list(_TARGETS)),
    default="agents",
    show_default=True,
    help="Predefined install location.",
)
@click.option(
    "--dir",
    "custom_dir",
    default=None,
    metavar="PATH",
    help="Custom base directory (overrides --target). Skill is written to PATH/treadstone-cli/SKILL.md.",
)
def install(target: str, custom_dir: str | None) -> None:
    """Install SKILL.md to an agent runner's skills directory.

    \b
    Predefined targets:
      agents   ~/.agents/skills/treadstone-cli/SKILL.md   (default, works with Cursor/Codex agents)
      cursor   ~/.cursor/skills/treadstone-cli/SKILL.md
      codex    ~/.codex/skills/treadstone-cli/SKILL.md
      project  .agents/skills/treadstone-cli/SKILL.md     (relative to current working directory)

    \b
    Examples:
      treadstone skills install
      treadstone skills install --target cursor
      treadstone skills install --dir ~/.my-agent-runner/skills
    """
    base = pathlib.Path(custom_dir).expanduser() if custom_dir else _TARGETS[target]
    dest = base / _SKILL_DIR_NAME / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(AGENT_GUIDE, encoding="utf-8")
    click.echo(f"Installed: {dest}")
