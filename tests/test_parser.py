import copy
import json
from datetime import timezone
from pathlib import Path

import pytest

from ffai.parser import (
    EspnParseError,
    find_my_team,
    parse_free_agents,
    parse_league,
    parse_pro_schedule,
)

FIXTURES = Path(__file__).parent / "fixtures"
MY_SWID = "{AAAAAAAA-0000-4000-8000-000000000001}"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def raw_league():
    return _load("league_view.json")


@pytest.fixture
def league(raw_league):
    return parse_league(raw_league)


# League


def test_league_basics(league):
    assert league.id == "1669256142"
    assert league.year == 2018
    assert league.name == "Fixture League"
    assert league.scoring_period == 1
    assert league.matchup_period == 1
    assert len(league.teams) == 3


def test_slot_counts_become_int_keys(league):
    # ESPN sends them as JSON keys, and a JSON key is a string.
    assert league.lineup_slot_counts[0] == 1  # QB
    assert league.lineup_slot_counts[23] == 1  # FLEX
    assert all(isinstance(k, int) for k in league.lineup_slot_counts)


def test_trade_deadline_is_utc(league):
    assert league.trade_deadline is not None
    assert league.trade_deadline.tzinfo == timezone.utc


def test_schedule_is_read(league):
    assert [(m.home_team_id, m.away_team_id) for m in league.schedule] == [(1, 2)]


def test_roster_entries_and_slots(league):
    team = league.teams[0]
    assert len(team.roster) == 15
    assert team.roster[0].lineup_slot_id == 4  # WR
    assert team.roster[0].player.name == "Antonio Brown"
    assert 4 in team.roster[0].player.eligible_slots


def test_team_name_from_location_and_nickname(league):
    assert league.teams[0].name == "Goin' HAM Newton"


def test_week_points_come_from_the_current_scoring_period(league):
    brown = league.teams[0].roster[0].player
    assert brown.projected_points is not None  # statSourceId 1, single week, week 1
    assert brown.actual_points == pytest.approx(24.3)  # statSourceId 0, single week, week 1
    assert brown.season_avg_projected == pytest.approx(21.458, abs=0.01)


def test_defense_without_injury_status_is_active(league):
    defenses = [e.player for t in league.teams for e in t.roster if e.player.position_id == 16]
    assert defenses
    assert all(p.injury_status == "ACTIVE" for p in defenses)


def test_missing_stats_give_none_not_a_crash(raw_league):
    for team in raw_league["teams"]:
        for entry in team["roster"]["entries"]:
            entry["playerPoolEntry"]["player"]["stats"] = []
    player = parse_league(raw_league).teams[0].roster[0].player
    assert player.projected_points is None
    assert player.actual_points is None


def test_stats_of_another_season_are_ignored(raw_league):
    for team in raw_league["teams"]:
        for entry in team["roster"]["entries"]:
            for row in entry["playerPoolEntry"]["player"]["stats"]:
                row["seasonId"] = 2017
    assert parse_league(raw_league).teams[0].roster[0].player.projected_points is None


# An ESPN format problem must be loud and readable


def test_missing_key_names_what_is_missing(raw_league):
    del raw_league["settings"]["rosterSettings"]["lineupSlotCounts"]
    with pytest.raises(EspnParseError, match="lineupSlotCounts"):
        parse_league(raw_league)


def test_missing_roster_view_is_explained(raw_league):
    del raw_league["teams"][0]["roster"]
    with pytest.raises(EspnParseError, match="mRoster"):
        parse_league(raw_league)


def test_not_a_dict_is_a_parse_error():
    with pytest.raises(EspnParseError):
        parse_league([])


# The team of the user


def test_my_team_is_found_by_swid(league):
    assert find_my_team(league, MY_SWID).id == 2


def test_swid_match_ignores_braces_and_case(league):
    assert find_my_team(league, "aaaaaaaa-0000-4000-8000-000000000001").id == 2


def test_explicit_team_id_wins_over_swid(league):
    assert find_my_team(league, MY_SWID, team_id="3").id == 3


def test_unknown_team_id_is_an_error(league):
    with pytest.raises(EspnParseError):
        find_my_team(league, MY_SWID, team_id="99")


def test_unknown_swid_is_an_error(league):
    with pytest.raises(EspnParseError, match="SWID"):
        find_my_team(league, "{NOT-MINE}")


# NFL schedule


def test_every_team_has_a_game_or_a_bye_per_week():
    games = parse_pro_schedule(_load("pro_schedule.json"))
    assert games
    assert all(g.kickoff.tzinfo == timezone.utc for g in games)
    in_week_1 = {g.pro_team_id for g in games if g.week == 1}
    # The NFL has 32 teams. ESPN uses id 0 for "no team".
    # A few teams are on a bye in week 1, or play outside the fixture window.
    # The test therefore checks the order of magnitude only.
    assert 20 <= len(in_week_1) <= 32


def test_each_game_is_listed_once_per_team():
    games = parse_pro_schedule(_load("pro_schedule.json"))
    keys = [(g.pro_team_id, g.week, g.kickoff) for g in games]
    assert len(keys) == len(set(keys))


def test_bye_week_means_no_game():
    # In 2024 no team has a bye before week 5.
    # The test makes a bye: it drops week 2 of team 12.
    raw = _load("pro_schedule.json")
    team = next(t for t in raw["settings"]["proTeams"] if t["id"] == 12)
    assert "2" in team["proGamesByScoringPeriod"]
    del team["proGamesByScoringPeriod"]["2"]
    weeks = {g.week for g in parse_pro_schedule(raw) if g.pro_team_id == 12}
    assert weeks == {1, 3, 4}


# Free agents


def test_free_agents(league):
    free_agents = parse_free_agents(_load("free_agents.json"), league.year, league.scoring_period)
    assert len(free_agents) == 12
    assert {fa.status for fa in free_agents} <= {"FREEAGENT", "WAIVERS"}
    gordon = next(fa for fa in free_agents if fa.player.name == "Josh Gordon")
    assert gordon.player.injury_status == "OUT"
    assert gordon.player.percent_owned == pytest.approx(76.51, abs=0.01)


def test_free_agents_without_players_key_is_a_parse_error():
    with pytest.raises(EspnParseError):
        parse_free_agents({}, 2026, 1)


def test_parsing_does_not_change_the_input(raw_league):
    before = copy.deepcopy(raw_league)
    parse_league(raw_league)
    assert raw_league == before
