# ==============================================================================
# alerts.py - turn analysis results into Alert objects   [STUB - SPEC step 5]
#
# Builds the alerts and their de-dup keys (SPEC 6.1) and the health alerts
# (SPEC 6.3). It does NOT send anything: cli/check passes new alerts to ai.py
# and notify.py, and calls store.mark_sent only after delivery.
# ==============================================================================
from ffai.analysis import FreeAgentMove
from ffai.lineup import LineupMove
from ffai.models import Alert


def lineup_alert(week: int, moves: tuple[LineupMove, ...], win_before: float, win_after: float) -> Alert:
    """Key: lineup:<week>:<the specific swaps>."""
    raise NotImplementedError("SPEC section 6.1")


def injury_alert(week: int, player_id: int, new_status: str, player_name: str) -> Alert:
    """Key: injury:<player>:<new status>:<week>."""
    raise NotImplementedError("SPEC section 6.1")


def free_agent_alert(week: int, move: FreeAgentMove) -> Alert:
    """Key: free_agent:<week>:<player>."""
    raise NotImplementedError("SPEC section 6.1")


def cookie_expired_alert() -> Alert:
    """Sent once, not on every run (use store.get_kv / set_kv)."""
    raise NotImplementedError("SPEC section 6.3")


def parse_failure_alert(detail: str) -> Alert:
    raise NotImplementedError("SPEC section 6.3")


def heartbeat_alert(last_ok_utc: str) -> Alert:
    """Weekly 'still alive' message."""
    raise NotImplementedError("SPEC section 6.3")
