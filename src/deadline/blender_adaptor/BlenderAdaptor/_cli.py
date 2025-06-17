# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import logging

from openjd.adaptor_runtime import EntryPoint

from .adaptor import BlenderAdaptor

__all__ = ["main"]

_logger = logging.getLogger(__name__)


def main(reentry_exe=None) -> int:
    """Entrypoint for the BlenderAdaptor."""
    try:
        EntryPoint(BlenderAdaptor).start(reentry_exe=reentry_exe)
    except Exception as e:
        _logger.error(f"Entrypoint failed: {e}")
        return 1

    _logger.info("Done BlenderAdaptor main")
    return 0
