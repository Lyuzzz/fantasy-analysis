# ==============================================================================
# analysis.py: numbers for expected points, win chance, ROS value and free agents
#                                   [STUB: SPEC steps 3-4, sections 5.2-5.5]
#
# Python computes every number in this module.
# The LLM (ai.py) only explains the numbers.
# The trade search (SPEC 5.6) is v2. It is NOT in this module yet.
# ==============================================================================
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ffai.lineup import LineupResult
from ffai.models import FreeAgent, Player, ProGame, Team


@dataclass(frozen=True)
class FreeAgentMove:
    add: Player
    drop: Player
    ros_gain_per_week: float
    week_gain: float
    tags: tuple[str, ...]  # "waiver", "recently_dropped", "rising"


def expected_points(player: Player, week: int, now: datetime, games: Sequence[ProGame]) -> float:
    """Return the expected points of a player this week.

    A finished game gives the actual points.
    A game in progress gives the actual points plus the projection times the time left.
    A game that has not started gives the projection.
    A player who is OUT, on IR, suspended or on a bye gets 0.
    A Doubtful or Questionable player gets a discount.
    """
    raise NotImplementedError("SPEC section 5.1")


def win_probability(mu_a: float, mu_b: float, var_a: float, var_b: float) -> float:
    """Return `Phi((mu_a - mu_b) / sqrt(var_a + var_b))`.

    The sigma of one player is about 0.45 x projection + 1.5.
    """
    raise NotImplementedError("SPEC section 5.2")


def ros_value(player: Player) -> float:
    """Return the weighted value per week for the rest of the season. Injury multipliers apply."""
    raise NotImplementedError("SPEC section 5.3")


def team_value(team: Team) -> float:
    """Return the total of the best lineup, using ROS values, plus 0.2 x the bench value."""
    raise NotImplementedError("SPEC section 5.3")


def evaluate_free_agents(
    team: Team,
    free_agents: Sequence[FreeAgent],
    current: LineupResult,
) -> list[FreeAgentMove]:
    """Try every free agent against every player that the user can drop.

    Keep the moves that pass the thresholds.
    """
    raise NotImplementedError("SPEC section 5.4")
