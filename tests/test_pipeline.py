import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ffai.parser import EspnParseError
from ffai.pipeline import analyze

FIXTURES = Path(__file__).parent / "fixtures"
MY_SWID = "{AAAAAAAA-0000-4000-8000-000000000001}"
# Week 1 of the 2024 fixture schedule starts on 2024-09-05 with a Thursday night game.
BEFORE_KICKOFFS = datetime(2024, 9, 1, tzinfo=timezone.utc)
AFTER_KICKOFFS = datetime(2024, 9, 20, tzinfo=timezone.utc)


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def payload():
    return {
        "league": _load("league_view.json"),
        "pro_schedule": _load("pro_schedule.json"),
        "free_agents": _load("free_agents.json"),
        "swid": MY_SWID,
    }


def test_result_has_my_team_and_the_league(payload):
    result = analyze(payload, now=BEFORE_KICKOFFS)
    assert result["team"]["id"] == 2
    assert result["league"] == {"id": "1669256142", "name": "Fixture League", "year": 2018, "week": 1}


def test_roster_is_split_into_starters_bench_and_ir(payload):
    result = analyze(payload, now=BEFORE_KICKOFFS)
    assert len(result["starters"]) + len(result["bench"]) + len(result["ir"]) == 15
    assert all(p["slot"] not in ("BE", "IR") for p in result["starters"])
    assert all(p["slot"] == "BE" for p in result["bench"])


def test_starters_are_in_display_order(payload):
    slots = [p["slot"] for p in analyze(payload, now=BEFORE_KICKOFFS)["starters"]]
    assert slots.index("QB") < slots.index("RB") < slots.index("WR") < slots.index("TE")
    assert slots.index("FLEX") > slots.index("TE")


def test_unfinished_work_is_listed_as_pending(payload):
    # The lineup optimizer does not exist yet. The result must say so.
    assert "best lineup" in analyze(payload, now=BEFORE_KICKOFFS)["pending"]


def test_free_agents_are_top_ten_by_ownership(payload):
    agents = analyze(payload, now=BEFORE_KICKOFFS)["free_agents"]
    assert len(agents) == 10
    owned = [a["percent_owned"] for a in agents]
    assert owned == sorted(owned, reverse=True)


def test_free_agents_are_optional(payload):
    del payload["free_agents"]
    assert analyze(payload, now=BEFORE_KICKOFFS)["free_agents"] == []


def test_the_result_is_json_serializable(payload):
    json.dumps(analyze(payload, now=BEFORE_KICKOFFS))


# Warnings


def _set_injury(payload, team_index, slot_id, status):
    for entry in payload["league"]["teams"][team_index]["roster"]["entries"]:
        if entry["lineupSlotId"] == slot_id:
            entry["playerPoolEntry"]["player"]["injuryStatus"] = status
            return entry["playerPoolEntry"]["player"]["fullName"]
    raise AssertionError("no such slot in the fixture")


def test_a_starter_who_is_out_raises_an_alert(payload):
    name = _set_injury(payload, 1, 0, "OUT")  # the QB of the user
    warnings = analyze(payload, now=BEFORE_KICKOFFS)["warnings"]
    assert {"level": "alert", "text": f"{name} (QB) is OUT and is in your starting lineup."} in warnings


def test_injury_reserve_and_suspension_count_as_out(payload):
    _set_injury(payload, 1, 0, "SUSPENSION")
    texts = [w["text"] for w in analyze(payload, now=BEFORE_KICKOFFS)["warnings"]]
    assert any("SUSPENSION" in t for t in texts)


def test_doubtful_and_questionable_are_softer(payload):
    _set_injury(payload, 1, 0, "DOUBTFUL")
    _set_injury(payload, 1, 6, "QUESTIONABLE")
    levels = {w["level"] for w in analyze(payload, now=BEFORE_KICKOFFS)["warnings"] if "Doubtful" in w["text"] or "Questionable" in w["text"]}
    assert levels == {"warning", "info"}


def test_an_injured_bench_player_is_not_a_warning(payload):
    for entry in payload["league"]["teams"][1]["roster"]["entries"]:
        if entry["lineupSlotId"] == 20:
            entry["playerPoolEntry"]["player"]["injuryStatus"] = "OUT"
    warnings = analyze(payload, now=BEFORE_KICKOFFS)["warnings"]
    assert not [w for w in warnings if w["level"] == "alert"]


def test_a_starter_on_bye_raises_an_alert(payload):
    team_id = next(
        e["playerPoolEntry"]["player"]["proTeamId"]
        for e in payload["league"]["teams"][1]["roster"]["entries"]
        if e["lineupSlotId"] == 0
    )
    schedule_team = next(t for t in payload["pro_schedule"]["settings"]["proTeams"] if t["id"] == team_id)
    del schedule_team["proGamesByScoringPeriod"]["1"]  # A team with no game in week 1 is on a bye.
    result = analyze(payload, now=BEFORE_KICKOFFS)
    assert any("bye" in w["text"] for w in result["warnings"])
    assert result["starters"][0]["bye"] is True


def test_an_empty_starting_slot_is_reported(payload):
    entries = payload["league"]["teams"][1]["roster"]["entries"]
    payload["league"]["teams"][1]["roster"]["entries"] = [e for e in entries if e["lineupSlotId"] != 0]
    texts = [w["text"] for w in analyze(payload, now=BEFORE_KICKOFFS)["warnings"]]
    assert "Empty QB slot (1 missing)." in texts


def test_a_clean_fixture_team_has_no_alerts(payload):
    # The fixture team is a real 2018 roster, so a clean lineup is possible.
    for team in payload["league"]["teams"]:
        for e in team["roster"]["entries"]:
            e["playerPoolEntry"]["player"]["injuryStatus"] = "ACTIVE"
    payload["pro_schedule"] = None
    warnings = analyze(payload, now=BEFORE_KICKOFFS)["warnings"]
    assert [w for w in warnings if w["level"] == "alert"] == []


def test_missing_schedule_is_stated_not_hidden(payload):
    del payload["pro_schedule"]
    texts = [w["text"] for w in analyze(payload, now=BEFORE_KICKOFFS)["warnings"]]
    assert any("schedule" in t for t in texts)


# Kickoff and locked state


def test_started_follows_the_kickoff_time(payload):
    for team in payload["league"]["teams"]:  # The 2018 fixture has stale lock flags.
        for e in team["roster"]["entries"]:
            e["playerPoolEntry"]["lineupLocked"] = False
    before = analyze(payload, now=BEFORE_KICKOFFS)["starters"]
    after = analyze(payload, now=AFTER_KICKOFFS)["starters"]
    assert not any(p["started"] for p in before)
    assert all(p["started"] for p in after if p["kickoff"])


# Bad requests


def test_not_a_json_object_is_rejected():
    with pytest.raises(EspnParseError):
        analyze([])


def test_a_request_without_league_is_rejected():
    with pytest.raises(EspnParseError, match="league"):
        analyze({})


def test_unknown_swid_is_a_clear_error(payload):
    payload["swid"] = "{NOT-ME}"
    with pytest.raises(EspnParseError, match="SWID"):
        analyze(payload, now=BEFORE_KICKOFFS)


def test_team_id_works_without_swid(payload):
    del payload["swid"]
    payload["team_id"] = 3
    assert analyze(payload, now=BEFORE_KICKOFFS)["team"]["id"] == 3


def test_analyze_does_not_change_the_input(payload):
    before = copy.deepcopy(payload)
    analyze(payload, now=BEFORE_KICKOFFS)
    assert payload == before
