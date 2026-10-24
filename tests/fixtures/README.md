# Test fixtures

These files are shorter copies of real ESPN responses.
They come from [cwendt94/espn-api](https://github.com/cwendt94/espn-api), under the MIT license.
The source folder is `tests/football/unit/data/`.
Each file keeps only the fields that `ffai.parser` reads.
Each file also keeps only the first teams and players.

| File | Source | Notes |
|---|---|---|
| `league_view.json` | `league_2018_data.json` and `league_roster_week1.json` | One merged response, in the shape that ESPN returns for `view=mSettings&view=mTeam&view=mRoster&view=mMatchupScore`. It holds 3 teams. The tests use the fake SWID `{AAAAAAAA-0000-4000-8000-000000000001}` as the user. That SWID owns team 2. The league id and the season have new values. |
| `free_agents.json` | `league_free_agents_2018.json` | The first 12 players of the `kona_player_info` response. |
| `pro_schedule.json` | `pro_schedule_2024.json` | The NFL teams, for weeks 1 to 4 only. |

The files hold no real league data, no cookies and no personal ids.
