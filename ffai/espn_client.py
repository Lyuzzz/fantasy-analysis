# ==============================================================================
# espn_client.py: HTTP calls to the unofficial ESPN API   [STUB: SPEC step 2]
#
# Each method matches one row of the SPEC section 4 table.
# Every call needs a timeout and retry.retry().
# The program does not use the espn_api library, because that library sets no timeouts.
# The methods return RAW JSON (dicts). parser.py turns the JSON into models.
# ==============================================================================
from collections.abc import Sequence


class EspnAuthError(Exception):
    """ESPN answered 401. The espn_s2 or SWID cookie is wrong or expired (SPEC 6.3)."""


class EspnClient:
    """One client for each league.

    The cookies belong to the account, so every league uses the same espn_s2 and SWID.
    The NFL schedule does not depend on the league.
    Fetch it once for each check, not once for each league.
    """

    def __init__(self, league_id: str, year: int, espn_s2: str, swid: str):
        self.league_id = league_id
        self.year = year
        self.espn_s2 = espn_s2
        self.swid = swid

    def get_league(self) -> dict:
        """The mSettings, mTeam, mRoster and mMatchupScore views."""
        raise NotImplementedError("SPEC section 4: league data")

    def get_pro_schedule(self) -> dict:
        """The proTeamSchedules_wl view. It has kickoff times and bye weeks."""
        raise NotImplementedError("SPEC section 4: NFL schedule")

    def get_free_agents(self, week: int, limit: int = 100) -> dict:
        """The kona_player_info view with the FREEAGENT and WAIVERS filter."""
        raise NotImplementedError("SPEC section 4: free agents")

    def get_player_stats(self, player_ids: Sequence[int], week: int) -> dict:
        """The kona_playercard view. Each request holds at most 40 ids."""
        raise NotImplementedError("SPEC section 4: weekly score history")

    def get_recent_drops(self) -> dict:
        """The communication view with the ACTIVITY_TRANSACTIONS filter."""
        raise NotImplementedError("SPEC section 4: recently dropped players")
