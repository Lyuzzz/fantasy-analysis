# ==============================================================================
# retry_util.py - small retry helper for flaky network calls
#
# Same helper as stock-ai's core/retry_util.py. Linear backoff: with the
# defaults it waits 2s, then 4s, and re-raises the last error on the third
# failure. Used for ESPN requests and SMTP; the caller decides what a final
# failure means.
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
        except Exception as e:  # noqa: BLE001 - the caller decides what is fatal
            last_error = e
            if attempt < tries:
                delay = base_delay * attempt
                logger.warning(f"{label} failed (attempt {attempt}/{tries}): {e} - retrying in {delay}s")
                time.sleep(delay)
    assert last_error is not None
    raise last_error
