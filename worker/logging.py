from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "[%(asctime)s] [%(process)d] [%(levelname)s] %(name)s | %(message)s"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def configure_logger(level: str | None = None) -> None:
    """Configure the global application logging.

    This initializes the root logger with a Gunicorn-style log format
    and attaches a stdout stream handler so all application logs share
    a consistent structure across workers and subprocesses.
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    root_logger = logging.getLogger()

    root_logger.setLevel(log_level)

    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    logging.captureWarnings(True)

    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
