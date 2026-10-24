# ==============================================================================
# parser.py - raw ESPN JSON -> models.py dataclasses   [STUB - SPEC step 2]
#
# Pure functions, no network. Test them against the real JSON files in
# cwendt94/espn-api (tests/football/unit/data/). When ESPN changes its format,
# raise EspnParseError so a health alert is sent (SPEC 6.3) instead of the
# program going quiet.
# ==============================================================================
from ffai.models import League, Player, ProGame, Team


class EspnParseError(Exception):
    """ESPN's response no longer matches what we expect."""


def parse_league(raw: dict) -> League:
    raise NotImplementedError("SPEC section 4: league data")


def parse_pro_schedule(raw: dict, year: int) -> tuple[ProGame, ...]:
    """Kickoffs for every NFL game. A missing week for a team means bye."""
    raise NotImplementedError("SPEC section 4: NFL schedule")


def parse_free_agents(raw: dict) -> tuple[Player, ...]:
    raise NotImplementedError("SPEC section 4: free agents")


def find_my_team(league: League, swid: str, team_id: str = "") -> Team:
    """The team whose owners include my SWID, or the explicit team id for this
    league (settings.team_id_for(league.id))."""
    raise NotImplementedError("SPEC section 4: my team")
