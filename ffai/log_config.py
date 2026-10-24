# ==============================================================================
# log_config.py: loguru setup. Logs go to stderr only, as in stock-ai.
#
# The json-file driver of Docker collects stderr and limits its size.
# The program therefore writes no log files.
# ==============================================================================
import logging
import os
import sys

from loguru import logger

# These libraries log every HTTP request at INFO level.
# Without this list, their lines hide the lines of the program.
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
