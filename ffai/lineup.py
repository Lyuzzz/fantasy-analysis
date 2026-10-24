# ==============================================================================
# lineup.py: the best lineup for the week   [STUB: SPEC step 3, section 5.1]
#
# The task is a matching of players to slots with the maximum total weight.
# Sort the players by expected points, from high to low.
# Add a player when an augmenting path exists (Kuhn's algorithm).
# A locked player first takes the current slot and cannot move.
# ==============================================================================
from collections.abc import Mapping
from dataclasses import dataclass

from ffai.models import Player, RosterEntry


@dataclass(frozen=True)
class LineupMove:
    start: Player
    bench: Player
    gain: float  # expected points


@dataclass(frozen=True)
class LineupResult:
    starters: Mapping[int, tuple[Player, ...]]  # maps a lineupSlotId to its players
    total_points: float
    moves: tuple[LineupMove, ...]
    warnings: tuple[str, ...]  # OUT, bye or empty slot in the CURRENT lineup


def optimize_lineup(
    roster: tuple[RosterEntry, ...],
    slot_counts: Mapping[int, int],
    expected_points: Mapping[int, float],  # maps a player id to points
    locked_ids: frozenset[int],
) -> LineupResult:
    raise NotImplementedError("SPEC section 5.1")
