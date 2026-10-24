# ==============================================================================
# lineup.py - best lineup for the week   [STUB - SPEC step 3, section 5.1]
#
# Maximum-weight matching of players to slots. Sort players by expected points
# (high to low) and add each one if an augmenting path exists (Kuhn's
# algorithm). Locked players first take their current slot and cannot move.
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
    starters: Mapping[int, tuple[Player, ...]]  # lineupSlotId -> players
    total_points: float
    moves: tuple[LineupMove, ...]
    warnings: tuple[str, ...]  # OUT / bye / empty slot in the CURRENT lineup


def optimize_lineup(
    roster: tuple[RosterEntry, ...],
    slot_counts: Mapping[int, int],
    expected_points: Mapping[int, float],  # player id -> points
    locked_ids: frozenset[int],
) -> LineupResult:
    raise NotImplementedError("SPEC section 5.1")
