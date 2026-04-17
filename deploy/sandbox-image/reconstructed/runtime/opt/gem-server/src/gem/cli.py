import logging
import os
import sys
from urllib.parse import urlparse

import click
import uvicorn


def setup_logging(level: str = "INFO") -> None:
    """
    Configure a general-purpose logger with millisecond timestamps (recommended).
    """
    # Format string: add ,%(msecs)03d after asctime to pad 3-digit milliseconds
    log_format = "[%(asctime)s.%(msecs)03d:%(levelname)s] %(message)s"
    # asctime format
    date_format = "%m%d/%H%M%S"

    # Use the standard Formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Get the root logger and configure it
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)


@click.command()
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=8088,
    help="Bind socket to this port. If 0, an available port will be picked.",
    show_default=True,
)
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
@click.option(
    "--ws-ping-interval",
    type=float,
    default=20.0,
    help="WebSocket ping interval in seconds.",
    show_default=True,
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["critical", "error", "warning", "info", "debug", "trace"], case_sensitive=False
    ),
    default="INFO",
    help="Log level.",
    show_default=True,
)
@click.option(
    "--cdp-origin",
    default="http://127.0.0.1:9222",
    help="The target CDP origin (e.g., http://127.0.0.1:9222) to proxy.",
    show_default=True,
)
def cli(
    host: str,
    port: int,
    reload: bool,
    ws_ping_interval: float,
    log_level: str,
    cdp_origin: str,
) -> None:
    """
    Starts the server to control environment and proxy CDP.
    """
    setup_logging(log_level)

    try:
        parsed_origin = urlparse(cdp_origin)
        if not all([parsed_origin.scheme in ("http", "https"), parsed_origin.netloc]):
            raise ValueError("Invalid origin format. It must include scheme and host.")

        if parsed_origin.path and parsed_origin.path != "/":
            raise ValueError("The origin should not contain a path.")

        netloc = parsed_origin.netloc

    except ValueError as e:
        logging.error(f"Error: Invalid --cdp-origin '{cdp_origin}'. {e}")
        sys.exit(1)

    clean_origin = cdp_origin.rstrip("/")
    os.environ["CDP_TARGET_ORIGIN"] = clean_origin
    os.environ["CDP_TARGET_NETLOC"] = netloc

    logging.info(
        f"Starting server at http://{host}:{port} with WebSocket ping interval {ws_ping_interval}s."
    )
    logging.info(f"Proxying CDP requests to {clean_origin}")
    uvicorn.run(
        "gem.server:api",
        host=host,
        port=port,
        ws_ping_interval=ws_ping_interval,
        reload=reload,
        log_config=None,
    )


if __name__ == "__main__":
    cli()
