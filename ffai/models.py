# ==============================================================================
# models.py - plain data classes shared by every module
#
# parser.py builds these from ESPN JSON; lineup.py and analysis.py only ever
# see these, never raw JSON. That keeps the maths testable with fake data.
# All classes are frozen (immutable), like a Java record.
# ==============================================================================
from dataclasses import dataclass, field
from datetime import datetime

# Alert kinds. They are also the first part of the de-dup key (SPEC 6.1).
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
    eligible_slots: tuple[int, ...]  # lineupSlotIds this player may fill
    pro_team_id: int
    # ESPN injuryStatus: ACTIVE, QUESTIONABLE, DOUBTFUL, OUT, INJURY_RESERVE, SUSPENSION
    injury_status: str = "ACTIVE"
    percent_owned: float = 0.0
    percent_change: float = 0.0


@dataclass(frozen=True)
class RosterEntry:
    player: Player
    lineup_slot_id: int  # 20 = bench, 21 = IR, anything else = a starting slot


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    owner_ids: tuple[str, ...]  # SWIDs, used to find "my" team
    roster: tuple[RosterEntry, ...]


@dataclass(frozen=True)
class Matchup:
    matchup_period: int
    home_team_id: int
    away_team_id: int


@dataclass(frozen=True)
class ProGame:
    """One NFL game. A team with no ProGame in a week is on bye."""

    pro_team_id: int
    week: int
    kickoff: datetime  # timezone-aware, UTC


@dataclass(frozen=True)
class League:
    id: str
    year: int
    scoring_period: int  # NFL week
    matchup_period: int  # NOT always equal to scoring_period (playoffs)
    lineup_slot_counts: dict[int, int]
    teams: tuple[Team, ...]
    schedule: tuple[Matchup, ...] = ()
    trade_deadline: datetime | None = None


@dataclass(frozen=True)
class Alert:
    """One message the user may need to act on."""

    kind: str
    key: str  # de-dup key, see SPEC 6.1
    title: str
    body: str
    urgent: bool = False  # urgent alerts ignore quiet hours
    week: int | None = None
    payload: dict = field(default_factory=dict)  # numbers for the AI step
