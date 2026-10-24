# ==============================================================================
# analysis.py - numbers: expected points, win chance, ROS, free agents
#                                          [STUB - SPEC steps 3-4, sections 5.2-5.5]
#
# Python computes every number here. The LLM (ai.py) only explains them.
# Trade search (SPEC 5.6) is v2 and is NOT part of this module yet.
# ==============================================================================
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ffai.lineup import LineupResult
from ffai.models import Player, ProGame, Team


@dataclass(frozen=True)
class FreeAgentMove:
    add: Player
    drop: Player
    ros_gain_per_week: float
    week_gain: float
    tags: tuple[str, ...]  # "waiver", "recently_dropped", "rising"


def expected_points(player: Player, week: int, now: datetime, games: Sequence[ProGame]) -> float:
    """Finished: actual. In progress: actual + projection x time left. Not started: projection.
    OUT / IR / suspended / bye: 0. Doubtful and Questionable are discounted."""
    raise NotImplementedError("SPEC section 5.1")


def win_probability(mu_a: float, mu_b: float, var_a: float, var_b: float) -> float:
    """Phi((mu_a - mu_b) / sqrt(var_a + var_b)); sigma per player ~ 0.45 x projection + 1.5."""
    raise NotImplementedError("SPEC section 5.2")


def ros_value(player: Player) -> float:
    """Weighted per-week value for the rest of the season, with injury multipliers."""
    raise NotImplementedError("SPEC section 5.3")


def team_value(team: Team) -> float:
    """Best-lineup total using ROS values + 0.2 x bench value."""
    raise NotImplementedError("SPEC section 5.3")


def evaluate_free_agents(
    team: Team,
    free_agents: Sequence[Player],
    current: LineupResult,
) -> list[FreeAgentMove]:
    """Try every free agent against every droppable player; keep moves over the thresholds."""
    raise NotImplementedError("SPEC section 5.4")
