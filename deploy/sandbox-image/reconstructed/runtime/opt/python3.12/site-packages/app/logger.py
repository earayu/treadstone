from __future__ import annotations

import logging
import sys


def setup_logging(level: str = 'INFO') -> None:
    """
    Configure a general-purpose logger with millisecond timestamps (recommended).
    """
    # Format string: add ,%(msecs)03d after asctime to pad 3-digit milliseconds
    log_format = '[%(asctime)s.%(msecs)03d:%(levelname)s] %(message)s'
    # asctime format
    date_format = '%m%d/%H%M%S'

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
