# ==============================================================================
# espn_client.py - HTTP calls to ESPN's unofficial API   [STUB - SPEC step 2]
#
# One method per row of the SPEC section 4 table. Every call needs a timeout
# and retry.retry(); the espn_api library has no timeouts, so we do not use it.
# Returns RAW JSON (dicts). Turning JSON into models is parser.py's job.
# ==============================================================================
from collections.abc import Sequence


class EspnAuthError(Exception):
    """ESPN answered 401: espn_s2 / SWID are wrong or expired (SPEC 6.3)."""


class EspnClient:
    """One client per league. The cookies belong to the account, so every
    league uses the same espn_s2 and SWID. The NFL schedule does not depend on
    the league: fetch it once per check, not once per league."""

    def __init__(self, league_id: str, year: int, espn_s2: str, swid: str):
        self.league_id = league_id
        self.year = year
        self.espn_s2 = espn_s2
        self.swid = swid

    def get_league(self) -> dict:
        """mSettings + mTeam + mRoster + mMatchupScore views."""
        raise NotImplementedError("SPEC section 4: league data")

    def get_pro_schedule(self) -> dict:
        """proTeamSchedules_wl view: kickoff times and bye weeks."""
        raise NotImplementedError("SPEC section 4: NFL schedule")

    def get_free_agents(self, week: int, limit: int = 100) -> dict:
        """kona_player_info view with the FREEAGENT / WAIVERS filter."""
        raise NotImplementedError("SPEC section 4: free agents")

    def get_player_stats(self, player_ids: Sequence[int], week: int) -> dict:
        """kona_playercard view; batches of at most 40 ids per request."""
        raise NotImplementedError("SPEC section 4: weekly score history")

    def get_recent_drops(self) -> dict:
        """communication view filtered to ACTIVITY_TRANSACTIONS."""
        raise NotImplementedError("SPEC section 4: recently dropped players")
