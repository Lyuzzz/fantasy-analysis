# ==============================================================================
# models.py: plain data classes that every module shares
#
# parser.py builds these classes from ESPN JSON.
# lineup.py and analysis.py see only these classes, never raw JSON.
# This keeps the maths testable with fake data.
# All classes are frozen, so nobody can change an object after it exists.
# A frozen class works like a Java record.
# ==============================================================================
from dataclasses import dataclass, field
from datetime import datetime

# Alert kinds. A kind is also part of a de-dup key (SPEC 6.1).
LINEUP = "lineup"
INJURY = "injury"
FREE_AGENT = "free_agent"
TRADE = "trade"  # v2
PREVIEW = "preview"  # v2
HEALTH = "health"


@dataclass(frozen=True)
class Player:
    id: int
    name: str
    position_id: int  # defaultPositionId: 1 QB, 2 RB, 3 WR, 4 TE, 5 K, 16 D/ST
    eligible_slots: tuple[int, ...]  # lineupSlotIds that the player can fill
    pro_team_id: int
    # ESPN injuryStatus: ACTIVE, QUESTIONABLE, DOUBTFUL, OUT, INJURY_RESERVE, SUSPENSION
    injury_status: str = "ACTIVE"
    percent_owned: float = 0.0
    percent_change: float = 0.0
    # Points use the scoring of the league. None means that ESPN sent no number.
    projected_points: float | None = None  # projection for this week
    actual_points: float | None = None  # actual points this week, after the game starts
    season_avg_actual: float | None = None  # average per game this season
    season_avg_projected: float | None = None  # ESPN projection per game for the full season


@dataclass(frozen=True)
class RosterEntry:
    player: Player
    lineup_slot_id: int  # 20 is the bench. 21 is IR. Any other number is a starting slot.
    locked: bool = False  # True after the game of the player starts. The user cannot move the player then.


@dataclass(frozen=True)
class FreeAgent:
    player: Player
    status: str  # "FREEAGENT": the user can add the player now. "WAIVERS": the user needs a claim.


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    owner_ids: tuple[str, ...]  # SWIDs. The program uses them to find the team of the user.
    roster: tuple[RosterEntry, ...]


@dataclass(frozen=True)
class Matchup:
    matchup_period: int
    home_team_id: int
    away_team_id: int


@dataclass(frozen=True)
class ProGame:
    """One NFL game. A team that has no ProGame in a week is on a bye."""

    pro_team_id: int
    week: int
    kickoff: datetime  # UTC time with a time zone


@dataclass(frozen=True)
class League:
    id: str
    year: int
    name: str
    scoring_period: int  # NFL week
    matchup_period: int  # Not always equal to scoring_period. The two differ in the playoffs.
    lineup_slot_counts: dict[int, int]
    teams: tuple[Team, ...]
    schedule: tuple[Matchup, ...] = ()
    trade_deadline: datetime | None = None


@dataclass(frozen=True)
class Alert:
    """One message that the user may need to act on."""

    kind: str
    key: str  # De-dup key (SPEC 6.1). The key of a league alert starts with the league id.
    title: str
    body: str
    urgent: bool = False  # An urgent alert ignores the quiet hours.
    week: int | None = None
    # Empty for an alert about the account (cookie expired, heartbeat).
    # The push title shows the league name, so the user knows which league the alert is about.
    league_id: str = ""
    league_name: str = ""
    payload: dict = field(default_factory=dict)  # numbers that the AI step reads
