# Test fixtures

Trimmed copies of real ESPN responses from [cwendt94/espn-api](https://github.com/cwendt94/espn-api) (MIT license),
`tests/football/unit/data/`. Only the fields `ffai.parser` reads were kept, and only the first teams / players.

| File | Source | Notes |
|---|---|---|
| `league_view.json` | `league_2018_data.json` + `league_roster_week1.json` | Merged into one payload, like ESPN returns for `view=mSettings&view=mTeam&view=mRoster&view=mMatchupScore`. 3 teams. Team 2's owner is the fake SWID `{AAAAAAAA-0000-4000-8000-000000000001}` that the tests use as "me". League id and season are rewritten. |
| `free_agents.json` | `league_free_agents_2018.json` | First 12 players of the `kona_player_info` response. |
| `pro_schedule.json` | `pro_schedule_2024.json` | NFL teams, weeks 1-4 only. |

No real league data, no cookies, no personal ids.
