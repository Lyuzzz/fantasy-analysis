# ==============================================================================
# alerts.py - turn analysis results into Alert objects   [STUB - SPEC step 5]
#
# Builds the alerts and their de-dup keys (SPEC 6.1) and the health alerts
# (SPEC 6.3). It does NOT send anything: cli/check passes new alerts to ai.py
# and notify.py, and calls store.mark_sent only after delivery.
# ==============================================================================
from ffai.analysis import FreeAgentMove
from ffai.lineup import LineupMove
from ffai.models import Alert, League

# With several leagues every league alert key starts with the league id, so the
# same player in two leagues never shares a key. Set Alert.league_id and
# Alert.league_name too (the name is shown in the push title).


def lineup_alert(
    league: League, moves: tuple[LineupMove, ...], win_before: float, win_after: float
) -> Alert:
    """Key: <league>:lineup:<week>:<the specific swaps>."""
    raise NotImplementedError("SPEC section 6.1")


def injury_alert(league: League, player_id: int, new_status: str, player_name: str) -> Alert:
    """Key: <league>:injury:<player>:<new status>:<week>."""
    raise NotImplementedError("SPEC section 6.1")


def free_agent_alert(league: League, move: FreeAgentMove) -> Alert:
    """Key: <league>:free_agent:<week>:<player>."""
    raise NotImplementedError("SPEC section 6.1")


def cookie_expired_alert() -> Alert:
    """Account-level (no league). Sent once, not on every run (use store.get_kv / set_kv)."""
    raise NotImplementedError("SPEC section 6.3")


def parse_failure_alert(detail: str) -> Alert:
    raise NotImplementedError("SPEC section 6.3")


def heartbeat_alert(last_ok_utc: str) -> Alert:
    """Weekly 'still alive' message."""
    raise NotImplementedError("SPEC section 6.3")
