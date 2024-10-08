# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

try:
    from deadline.client import config
except ImportError:
    pass

_DEFAULT_FORMATTER = logging.Formatter(
    fmt="%(asctime)s %(levelname)8s {%(threadName)-10s}:  %(module)s %(funcName)s: %(message)s",
)


def add_file_handler(
    file: Optional[Path] = None,
    logger: logging.Logger = logging.getLogger(),
    fmt: logging.Formatter = _DEFAULT_FORMATTER,
    level=logging.DEBUG,
):
    """Configure and add a file handler to the specified logger.

    If a handler with the same output file already exists on the logger, replace it.

    Args:
        file: The file to log to. Defaults to a file at `~/.deadline/logs/blender`.
        logger: The logger to add the handler to. Defaults to the root logger.
        fmt: The format string to use for the log messages on the new handler.
        level: The level to set the handler to. Defaults to DEBUG.
    """

    if file is None:
        file = Path.home() / ".deadline" / "logs" / "submitters" / "blender.log"
        file.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(file, maxBytes=10485760, backupCount=5)
    handler.setFormatter(fmt)
    handler.setLevel(level)

    # Find the handlers with the same file as the one we're adding, if any, and remove it.
    existing = []
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == handler.baseFilename:
            existing.append(h)
    for h in existing:
        logger.removeHandler(h)
        logger.info(f"Removed existing file handler: {h}")

    logger.addHandler(handler)
    logger.info(f"Added file handler to handlers: {logger.handlers}")


def get_deadline_config_level():
    """Get the current log level set in the Deadline configuration file."""
    return config.config_file.get_setting("settings.log_level")
