# ==============================================================================
# parser.py - raw ESPN JSON -> models.py dataclasses
#
# Pure functions, no network. They accept ONE merged league response, the same
# shape ESPN returns for ?view=mSettings&view=mTeam&view=mRoster&view=mMatchupScore.
# Tests use trimmed real responses from cwendt94/espn-api (tests/fixtures/).
#
# When ESPN changes its format we raise EspnParseError with a clear message, so
# the caller can tell the user (side panel now, a health alert later - SPEC 6.3)
# instead of the program going quiet.
# ==============================================================================
from datetime import datetime, timezone
from typing import Any

from ffai.models import FreeAgent, League, Matchup, Player, ProGame, RosterEntry, Team


class EspnParseError(Exception):
    """ESPN's response no longer matches what we expect."""


def _need(raw: dict, key: str, where: str) -> Any:
    try:
        return raw[key]
    except (KeyError, TypeError):
        raise EspnParseError(f"ESPN response has no '{key}' in {where}") from None


def _ms_to_utc(ms: int | float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _norm_swid(swid: str) -> str:
    """'{abc-1}' and 'ABC-1' compare equal."""
    return swid.strip().strip("{}").lower()


# --- players ---


def _stat_value(stats: list[dict], year: int, *, source: int, split: int, period: int, field: str) -> float | None:
    """One number from player.stats[].

    statSourceId: 0 actual, 1 projected. statSplitTypeId: 0 whole season, 1 single week.
    scoringPeriodId 0 is the whole-season row. Rows of other seasons are ignored.
    """
    for row in stats:
        if (
            row.get("seasonId", year) == year
            and row.get("statSourceId") == source
            and row.get("statSplitTypeId") == split
            and row.get("scoringPeriodId") == period
            and row.get(field) is not None
        ):
            return float(row[field])
    return None


def _parse_player(raw: dict, year: int, week: int) -> Player:
    try:
        stats = raw.get("stats") or []
        ownership = raw.get("ownership") or {}
        return Player(
            id=int(raw["id"]),
            name=raw.get("fullName") or f"{raw.get('firstName', '')} {raw.get('lastName', '')}".strip(),
            position_id=int(raw["defaultPositionId"]),
            eligible_slots=tuple(int(s) for s in raw["eligibleSlots"]),
            pro_team_id=int(raw.get("proTeamId", 0)),
            # D/ST rows often have no injuryStatus at all.
            injury_status=raw.get("injuryStatus") or "ACTIVE",
            percent_owned=float(ownership.get("percentOwned") or 0.0),
            percent_change=float(ownership.get("percentChange") or 0.0),
            projected_points=_stat_value(stats, year, source=1, split=1, period=week, field="appliedTotal"),
            actual_points=_stat_value(stats, year, source=0, split=1, period=week, field="appliedTotal"),
            season_avg_actual=_stat_value(stats, year, source=0, split=0, period=0, field="appliedAverage"),
            season_avg_projected=_stat_value(stats, year, source=1, split=0, period=0, field="appliedAverage"),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise EspnParseError(f"cannot read a player: {e!r}") from None


def _parse_entry(raw: dict, year: int, week: int) -> RosterEntry:
    pool = _need(raw, "playerPoolEntry", "a roster entry")
    return RosterEntry(
        player=_parse_player(_need(pool, "player", "a roster entry"), year, week),
        lineup_slot_id=int(_need(raw, "lineupSlotId", "a roster entry")),
        locked=bool(pool.get("lineupLocked", False)),
    )


# --- league ---


def _parse_team(raw: dict, year: int, week: int) -> Team:
    name = raw.get("name") or f"{raw.get('location', '')} {raw.get('nickname', '')}".strip()
    entries = (raw.get("roster") or {}).get("entries")
    if entries is None:
        raise EspnParseError(f"team {raw.get('id')} has no roster: was view=mRoster requested?")
    return Team(
        id=int(_need(raw, "id", "a team")),
        name=name or f"Team {raw['id']}",
        owner_ids=tuple(str(o) for o in raw.get("owners") or ()),
        roster=tuple(_parse_entry(e, year, week) for e in entries),
    )


def parse_league(raw: dict) -> League:
    year = int(_need(raw, "seasonId", "the league"))
    week = int(_need(raw, "scoringPeriodId", "the league"))
    settings = _need(raw, "settings", "the league")
    counts = _need(_need(settings, "rosterSettings", "settings"), "lineupSlotCounts", "rosterSettings")
    deadline = (settings.get("tradeSettings") or {}).get("deadlineDate")
    return League(
        id=str(_need(raw, "id", "the league")),
        year=year,
        name=settings.get("name") or "",
        scoring_period=week,
        matchup_period=int(_need(_need(raw, "status", "the league"), "currentMatchupPeriod", "status")),
        # ESPN sends the slot ids as JSON object keys, which are always strings.
        lineup_slot_counts={int(slot): int(n) for slot, n in counts.items()},
        teams=tuple(_parse_team(t, year, week) for t in _need(raw, "teams", "the league")),
        schedule=tuple(
            Matchup(
                matchup_period=int(m["matchupPeriodId"]),
                home_team_id=int(m["home"]["teamId"]),
                away_team_id=int(m["away"]["teamId"]),
            )
            for m in raw.get("schedule") or ()
            if "home" in m and "away" in m  # a bye week has only one side
        ),
        trade_deadline=_ms_to_utc(deadline) if deadline else None,
    )


def find_my_team(league: League, swid: str, team_id: str = "") -> Team:
    """The team whose owners include my SWID, or the explicit team id for this
    league (settings.team_id_for(league.id))."""
    if team_id:
        for team in league.teams:
            if str(team.id) == str(team_id):
                return team
        raise EspnParseError(f"league {league.id} has no team with id {team_id}")
    if swid:
        wanted = _norm_swid(swid)
        for team in league.teams:
            if any(_norm_swid(o) == wanted for o in team.owner_ids):
                return team
    raise EspnParseError(f"none of the teams in league {league.id} is owned by this account (SWID)")


# --- NFL schedule and free agents ---


def parse_pro_schedule(raw: dict) -> tuple[ProGame, ...]:
    """Kickoffs for every NFL game. A team with no game in a week is on bye."""
    games: list[ProGame] = []
    pro_teams = _need(_need(raw, "settings", "the NFL schedule"), "proTeams", "settings")
    for team in pro_teams:
        for week, week_games in (team.get("proGamesByScoringPeriod") or {}).items():
            for g in week_games:
                # Each game appears under both teams. Keep this team's side only.
                if team["id"] in (g["homeProTeamId"], g["awayProTeamId"]):
                    games.append(ProGame(pro_team_id=int(team["id"]), week=int(week), kickoff=_ms_to_utc(g["date"])))
    return tuple(games)


def parse_pro_team_names(raw: dict) -> dict[int, str]:
    """proTeamId -> abbreviation, from the same NFL schedule response."""
    pro_teams = _need(_need(raw, "settings", "the NFL schedule"), "proTeams", "settings")
    return {int(t["id"]): t.get("abbrev", "") for t in pro_teams if "id" in t}


def parse_free_agents(raw: dict, year: int, week: int) -> tuple[FreeAgent, ...]:
    players = _need(raw, "players", "the free-agent list")
    return tuple(
        FreeAgent(
            player=_parse_player(_need(p, "player", "a free agent"), year, week),
            status=p.get("status") or "FREEAGENT",
        )
        for p in players
    )
