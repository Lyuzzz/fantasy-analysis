# ==============================================================================
# scheduler.py: decide when to run and when to stay quiet   [STUB: SPEC step 5]
#
# The `check` command calls should_run_now() itself (SPEC 6.2).
# The Docker loop can then wake every 10 minutes, and this module decides whether work exists.
# The schedule follows the real NFL kickoff times. It does not use fixed weekdays.
# All times that go in and out are UTC datetimes with a time zone.
# ==============================================================================
from collections.abc import Sequence
from datetime import datetime

from ffai.models import ProGame


def should_run_now(now: datetime, games: Sequence[ProGame], lead_hours: float, last_run: datetime | None) -> bool:
    """Return True when the check should run now.

    The active window lasts from `lead_hours` before the first kickoff of a game day
    until 4 hours after the last kickoff. In this window, run every 10 minutes.
    Outside the window, run every 60 minutes.
    """
    raise NotImplementedError("SPEC section 6.2")


def in_quiet_hours(now: datetime, timezone_name: str, quiet_hours: tuple[int, int]) -> bool:
    """True inside the local-time window. For example, (23, 8) means 23:00 to 08:00."""
    raise NotImplementedError("SPEC section 6.2")
