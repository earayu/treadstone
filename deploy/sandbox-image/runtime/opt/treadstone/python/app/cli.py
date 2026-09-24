from __future__ import annotations

import logging

from app.logger import setup_logging
# Bootstrap logging before heavy imports so we capture the exact start time
setup_logging('INFO')
bootstrap_logger = logging.getLogger(__name__)
bootstrap_logger.info('python-server bootstrap start')

import os

import click


@click.command()
@click.option(
    '--host',
    type=str,
    default='127.0.0.1',
    help='Bind socket to this host.',
    show_default=True,
)
@click.option(
    '--port',
    type=int,
    default=8091,
    help='Bind socket to this port. If 0, an available port will be picked.',
    show_default=True,
)
@click.option('--reload', is_flag=True, default=False, help='Enable auto-reload.')
@click.option(
    '--ws-ping-interval',
    type=float,
    default=20.0,
    help='WebSocket ping interval in seconds.',
    show_default=True,
)
@click.option(
    '--log-level',
    type=click.Choice(
        ['critical', 'error', 'warning', 'info', 'debug', 'trace'], case_sensitive=False
    ),
    default='INFO',
    help='Log level.',
    show_default=True,
)
@click.option(
    '--workspace',
    type=str,
    default='/tmp',
    help='Path to the workspace directory.',
    show_default=True,
)
def cli(
    host: str,
    port: int,
    reload: bool,
    ws_ping_interval: float,
    log_level: str,
    workspace: str,
) -> None:
    """
    Starts the server to control sandbox environment.
    """
    log_level = 'DEBUG' if reload else log_level
    setup_logging(log_level)
    logging.info(f'Log level: {log_level}')

    os.environ['LOG_LEVEL'] = log_level
    os.environ['OTEL_SDK_DISABLED'] = 'true'

    if workspace:
        os.environ['WORKSPACE'] = workspace

    logging.info(f'Starting server at http://{host}:{port}.')

    # Production optimizations
    production_config = {
        'app': 'app.server:create_app',
        'factory': True,
        'host': host,
        'port': port,
        'reload': reload,
        'ws_ping_interval': ws_ping_interval,
        'log_config': None,
        'log_level': 'debug',
    }

    # Development mode: optimize for fast reload
    if reload:
        production_config.update(
            {
                'reload_delay': 0.25,  # 减少 reload 延迟到 250ms（默认 0.25s）
                'timeout_graceful_shutdown': 1,  # 优雅关闭超时 1 秒（默认 None）
            }
        )
    else:
        # Add production optimizations when not in development
        production_config.update(
            {
                'log_level': 'info',
                'workers': 1,  # Single worker for async apps with shared state
                'loop': 'uvloop',  # Use uvloop for better async performance
                'access_log': False,  # Disable access logs for better performance
                'server_header': False,  # Remove server header
                'date_header': False,  # Remove date header
            }
        )

    logging.info('import uvicorn start')
    from uvicorn import run as uvicorn_run
    logging.info('import uvicorn done')

    uvicorn_run(**production_config)


if __name__ == '__main__':
    cli()
