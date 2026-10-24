# ==============================================================================
# scheduler.py - when to run and when to stay quiet   [STUB - SPEC step 5]
#
# `check` calls should_run_now() itself (SPEC 6.2), so the Docker loop can wake
# every 10 minutes and this module decides if there is work. The cadence comes
# from the real NFL kickoff times, not from hard-coded weekdays.
# All times in and out are timezone-aware UTC datetimes.
# ==============================================================================
from collections.abc import Sequence
from datetime import datetime

from ffai.models import ProGame


def should_run_now(now: datetime, games: Sequence[ProGame], lead_hours: float, last_run: datetime | None) -> bool:
    """Active window (every 10 min): from `lead_hours` before the first kickoff of a
    game day until the last kickoff + 4h. Otherwise every 60 min."""
    raise NotImplementedError("SPEC section 6.2")


def in_quiet_hours(now: datetime, timezone_name: str, quiet_hours: tuple[int, int]) -> bool:
    """True inside the local-time window, e.g. (23, 8) = 23:00 to 08:00."""
    raise NotImplementedError("SPEC section 6.2")
