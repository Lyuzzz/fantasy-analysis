# ==============================================================================
# alerts.py: turn analysis results into Alert objects   [STUB: SPEC step 5]
#
# This module builds the alerts and their de-dup keys (SPEC 6.1).
# It also builds the health alerts (SPEC 6.3).
# It does NOT send anything.
# The check command passes new alerts to ai.py and notify.py.
# The check command calls store.mark_sent only after delivery.
# ==============================================================================
from ffai.analysis import FreeAgentMove
from ffai.lineup import LineupMove
from ffai.models import Alert, League

# With several leagues, every league alert key starts with the league id.
# The same player in two leagues then never shares a key.
# Also set Alert.league_id and Alert.league_name. The push title shows the name.


def lineup_alert(
    league: League, moves: tuple[LineupMove, ...], win_before: float, win_after: float
) -> Alert:
    """Key: <league>:lineup:<week>:<the swaps>."""
    raise NotImplementedError("SPEC section 6.1")


def injury_alert(league: League, player_id: int, new_status: str, player_name: str) -> Alert:
    """Key: <league>:injury:<player>:<new status>:<week>."""
    raise NotImplementedError("SPEC section 6.1")


def free_agent_alert(league: League, move: FreeAgentMove) -> Alert:
    """Key: <league>:free_agent:<week>:<player>."""
    raise NotImplementedError("SPEC section 6.1")


def cookie_expired_alert() -> Alert:
    """An alert about the account, with no league.

    Send it once, not on every run (use store.get_kv and store.set_kv).
    """
    raise NotImplementedError("SPEC section 6.3")


def parse_failure_alert(detail: str) -> Alert:
    raise NotImplementedError("SPEC section 6.3")


def heartbeat_alert(last_ok_utc: str) -> Alert:
    """A weekly message that says the program is still running."""
    raise NotImplementedError("SPEC section 6.3")
