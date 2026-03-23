"""Entry point for `python -m treadstone.cli` and PyInstaller builds."""

from treadstone.cli._output import friendly_exception_handler
from treadstone.cli.main import cli

if __name__ == "__main__":
    friendly_exception_handler(cli)()
