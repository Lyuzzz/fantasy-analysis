# ==============================================================================
# log_config.py - loguru setup (stderr only, like stock-ai)
#
# Docker's json-file driver collects stderr and caps its size, so we do not
# write log files ourselves.
# ==============================================================================
import logging
import os
import sys

from loguru import logger

# Libraries that log every HTTP request at INFO level. They would bury our
# own lines during the 10-minute check cycle.
_NOISY = ["urllib3", "requests", "httpx", "httpcore", "asyncio"]


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
    )
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)
