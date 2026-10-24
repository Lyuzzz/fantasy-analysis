# ==============================================================================
# retry_util.py: a small retry helper for network calls that can fail
#
# This helper is the same as core/retry_util.py in stock-ai.
# It waits longer after each failure. With the defaults it waits 2 seconds,
# then 4 seconds. After the third failure it raises the last error.
# The program uses it for ESPN requests and SMTP.
# The caller decides what a final failure means.
# ==============================================================================
import time
from collections.abc import Callable
from typing import TypeVar

from loguru import logger

T = TypeVar("T")


def retry(fn: Callable[[], T], *, tries: int = 3, base_delay: float = 2, label: str = "call") -> T:
    last_error: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            # The caller decides which errors are fatal, so this code catches all of them.
            last_error = e
            if attempt < tries:
                delay = base_delay * attempt
                logger.warning(f"{label} failed (attempt {attempt}/{tries}): {e} - retrying in {delay}s")
                time.sleep(delay)
    assert last_error is not None
    raise last_error
