# ==============================================================================
# constants.py - ESPN id tables (SPEC section 4, "ID tables")
#
# Copied from espn_api's football/constant.py, which is the reference for
# these numbers. ESPN has not changed them in years, but an unknown id must
# never crash a run: use the *_name helpers, which fall back to the number.
# ==============================================================================

# lineupSlotId -> label
SLOT_NAMES = {
    0: "QB", 1: "TQB", 2: "RB", 3: "RB/WR", 4: "WR", 5: "WR/TE", 6: "TE", 7: "OP",
    8: "DT", 9: "DE", 10: "LB", 11: "DL", 12: "CB", 13: "S", 14: "DB", 15: "DP",
    16: "D/ST", 17: "K", 18: "P", 19: "HC", 20: "BE", 21: "IR", 23: "FLEX",
}  # fmt: skip

BENCH_SLOT = 20
IR_SLOT = 21

# Order used when showing the starting lineup.
SLOT_DISPLAY_ORDER = [0, 2, 4, 6, 23, 3, 5, 7, 16, 17]

# defaultPositionId -> label
POSITION_NAMES = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}

# Injury statuses that mean "will not play" (SPEC 5.1).
OUT_STATUSES = {"OUT", "INJURY_RESERVE", "SUSPENSION"}


def slot_name(slot_id: int) -> str:
    return SLOT_NAMES.get(slot_id, f"slot {slot_id}")


def position_name(position_id: int) -> str:
    return POSITION_NAMES.get(position_id, f"pos {position_id}")
