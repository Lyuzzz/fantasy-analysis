# ==============================================================================
# pipeline.py: the one entry point for analysis. Raw ESPN JSON goes in. A result comes out.
#
# This module is the seam between "where the data comes from" and "what the program does with it".
# Today the Chrome extension fetches the JSON with the ESPN login of the user.
# The extension POSTs the JSON to service.py.
# Later the background `check` can fetch the JSON with EspnClient and call the same analyze().
#
# analyze() is a pure function.
# It uses no network, no database and no clock, except `now`.
# The result holds only JSON types.
# The service can return it unchanged, and the AI step can read it.
#
# Done so far: parse, the team of the user, lineup display, warnings (OUT, bye, empty slot).
# Still to add (SPEC steps 3-4): lineup optimizer, win chance, free-agent scoring.
# The result lists them under "pending".
# No screen can then pretend that the lineup is optimal when nobody checked.
# ==============================================================================
from datetime import datetime, timezone

from ffai.constants import (
    BENCH_SLOT,
    IR_SLOT,
    OUT_STATUSES,
    SLOT_DISPLAY_ORDER,
    position_name,
    slot_name,
)
from ffai.models import League, RosterEntry
from ffai.parser import (
    EspnParseError,
    find_my_team,
    parse_free_agents,
    parse_league,
    parse_pro_schedule,
    parse_pro_team_names,
)

PENDING = ["best lineup", "win probability", "free-agent scoring"]
FREE_AGENT_LIST_SIZE = 10


def analyze(payload: dict, now: datetime | None = None) -> dict:
    if not isinstance(payload, dict):
        raise EspnParseError("the request must be a JSON object")
    if "league" not in payload:
        raise EspnParseError("the request has no 'league' (the ESPN league response)")
    now = now or datetime.now(timezone.utc)

    league = parse_league(payload["league"])
    team = find_my_team(league, str(payload.get("swid") or ""), str(payload.get("team_id") or ""))

    # Without the NFL schedule, the program cannot find bye weeks or kickoffs.
    # The result says so. It does not report "no problems" in silence.
    week_kickoffs: dict[int, datetime] | None = None
    pro_names: dict[int, str] = {}
    if payload.get("pro_schedule"):
        games = parse_pro_schedule(payload["pro_schedule"])
        pro_names = parse_pro_team_names(payload["pro_schedule"])
        week_kickoffs = {g.pro_team_id: g.kickoff for g in games if g.week == league.scoring_period}

    def view(entry: RosterEntry) -> dict:
        return _player_view(entry, week_kickoffs, pro_names, now)

    starters = [e for e in team.roster if e.lineup_slot_id not in (BENCH_SLOT, IR_SLOT)]
    starters.sort(key=_slot_order)
    bench = [e for e in team.roster if e.lineup_slot_id == BENCH_SLOT]
    ir = [e for e in team.roster if e.lineup_slot_id == IR_SLOT]

    result = {
        "league": {"id": league.id, "name": league.name, "year": league.year, "week": league.scoring_period},
        "team": {"id": team.id, "name": team.name},
        "starters": [view(e) for e in starters],
        "bench": [view(e) for e in bench],
        "ir": [view(e) for e in ir],
        "warnings": _warnings(league, starters, [view(e) for e in starters], week_kickoffs is not None),
        "free_agents": [],
        "pending": list(PENDING),
    }
    if payload.get("free_agents"):
        agents = parse_free_agents(payload["free_agents"], league.year, league.scoring_period)
        top = sorted(agents, key=lambda fa: fa.player.percent_owned, reverse=True)[:FREE_AGENT_LIST_SIZE]
        result["free_agents"] = [
            {
                "id": fa.player.id,
                "name": fa.player.name,
                "position": position_name(fa.player.position_id),
                "pro_team": pro_names.get(fa.player.pro_team_id, ""),
                "status": fa.status,
                "injury": fa.player.injury_status,
                "percent_owned": round(fa.player.percent_owned, 1),
                "percent_change": round(fa.player.percent_change, 1),
                "projected": fa.player.projected_points,
            }
            for fa in top
        ]
    return result


def _slot_order(entry: RosterEntry) -> int:
    slot = entry.lineup_slot_id
    return SLOT_DISPLAY_ORDER.index(slot) if slot in SLOT_DISPLAY_ORDER else len(SLOT_DISPLAY_ORDER) + slot


def _player_view(
    entry: RosterEntry, week_kickoffs: dict[int, datetime] | None, pro_names: dict[int, str], now: datetime
) -> dict:
    p = entry.player
    kickoff = week_kickoffs.get(p.pro_team_id) if week_kickoffs is not None else None
    # pro_team_id 0 means "no NFL team". That is not a bye.
    on_bye = week_kickoffs is not None and p.pro_team_id != 0 and kickoff is None
    return {
        "id": p.id,
        "name": p.name,
        "position": position_name(p.position_id),
        "pro_team": pro_names.get(p.pro_team_id, ""),
        "slot": slot_name(entry.lineup_slot_id),
        "injury": p.injury_status,
        "projected": p.projected_points,
        "actual": p.actual_points,
        "season_avg": p.season_avg_actual,
        "bye": on_bye,
        "kickoff": kickoff.isoformat() if kickoff else None,
        # ESPN sends lineupLocked. The kickoff check covers a stale flag.
        "started": bool(entry.locked or (kickoff is not None and now >= kickoff)),
    }


def _warnings(league: League, starters: list[RosterEntry], views: list[dict], have_schedule: bool) -> list[dict]:
    out: list[dict] = []

    for entry, v in zip(starters, views, strict=True):
        who = f"{v['name']} ({v['slot']})"
        if v["injury"] in OUT_STATUSES:
            out.append({"level": "alert", "text": f"{who} is {v['injury']} and is in your starting lineup."})
        elif v["bye"]:
            out.append({"level": "alert", "text": f"{who} is on a bye this week."})
        elif v["injury"] == "DOUBTFUL":
            out.append({"level": "warning", "text": f"{who} is Doubtful."})
        elif v["injury"] == "QUESTIONABLE":
            out.append({"level": "info", "text": f"{who} is Questionable."})

    # Find a starting slot that holds fewer players than the league requires.
    filled: dict[int, int] = {}
    for entry in starters:
        filled[entry.lineup_slot_id] = filled.get(entry.lineup_slot_id, 0) + 1
    for slot, needed in league.lineup_slot_counts.items():
        if slot in (BENCH_SLOT, IR_SLOT) or needed <= 0:
            continue
        missing = needed - filled.get(slot, 0)
        if missing > 0:
            out.append({"level": "alert", "text": f"Empty {slot_name(slot)} slot ({missing} missing)."})

    if not have_schedule:
        out.append({"level": "info", "text": "NFL schedule was not sent, so bye weeks and kickoff times were not checked."})
    return out
