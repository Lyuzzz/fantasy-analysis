# fantasy-analysis: an assistant for the lineup, free agents and trades of an ESPN fantasy team

> Project brief for Claude Code. Ask me about each `[CONFIRM]` item before you build it.

---

## 0. Architecture: Chrome extension and local service first, background program later

**Current phase.**
The first front end is a **Chrome extension** with a side panel.
The extension runs an analysis **only when I press a button**.
There is no always-on background run and no email for now.
The background program comes back after I understand how the ESPN login cookie behaves.
The cookie expires, and handling it is awkward.

```
Chrome extension (side panel)                 local service (Python, 127.0.0.1:8765)
  fetch ESPN with my browser login  ──raw JSON──>  ffai.pipeline.analyze(payload)
  render the result                 <──result────      parse, my team, checks (lineup, win%, free agents later)
                                                               ^
future background `check` (cookie via EspnClient) ─────────────┘  same analyze()
```

- **The extension does not handle cookies.**
  I am already logged in to ESPN in Chrome.
  The extension has host permission for `*.espn.com`. It calls the ESPN API, and the browser attaches the cookies.
  The extension never reads, stores or sends `espn_s2`.
  It reads one value: `SWID`. `SWID` identifies me and helps to find my team. It is not a login credential.
  When ESPN answers 401, the panel says "log in to ESPN".
- **One codebase does the analysis.**
  `analyze(payload)` in `ffai/pipeline.py` takes raw ESPN JSON and returns data that is ready for JSON.
  Today the extension supplies the JSON. Later the background `check` can supply it with `EspnClient`.
  `lineup.py` and `analysis.py` do not know where the data comes from.
- **An analysis runs only when I press a button.**
  Opening the panel sends no ESPN request. It sends only a local ping that tests whether the service runs.
  "Explain with AI" is a second button, so I always choose when the LLM costs money.
- **The AI settings live in the panel.**
  The panel has the provider, the API key, the model and the base URL.
  Chrome saves the key in `chrome.storage.local` and does not encrypt it.
  The panel sends the key only to `127.0.0.1`. The service passes the key to the AI provider.
  The service never stores or logs the key.
  `AI_*` in `.env` is only a fallback.
- **The background program will run on the same VM as stock-ai.**
  It has its own repo and its own Docker Compose project.
  It does not run inside the compose file or the process of stock-ai (section 13).
- A warning has a level: `alert`, `warning` or `info`. This level is not the same as an Alert.
  An Alert is a message that the program pushes in the background phase.

### Local service API (`python -m ffai serve`, loopback only)

| Route | Request body | Answer |
|---|---|---|
| `GET /health` | none | `{"ok": true}` |
| `POST /analyze` | `{"league": <ESPN league JSON, views mSettings+mTeam+mRoster+mMatchupScore>, "pro_schedule": <proTeamSchedules_wl JSON>, "free_agents": <kona_player_info JSON, optional>, "swid": "{...}", "team_id": "16" (optional)}` | the analysis result (below) |
| `POST /explain` | `{"result": <an /analyze result>, "ai": {"provider": "anthropic"\|"openai", "api_key", "model", "base_url"}}` | `{"text", "source": "ai"\|"template", "error"}` |

The service answers with these errors:
- `422` with `kind: "parse"` for an ESPN format problem or an unknown SWID.
- `400` for bad JSON.
- `413` for a body over 16 MB.
- `415` for a wrong content type.
- `403` for a wrong Host or Origin.
- `500` for an internal error. The details appear only in the service log.

The service accepts only `chrome-extension://` origins. `EXTENSION_ID` pins one extension.

**The analysis result** (`/analyze`) has these fields:
- `league {id, name, year, week}` and `team {id, name}`.
- `starters[]`, `bench[]` and `ir[]`. Each player has `name, position, pro_team, slot, injury, projected, actual, season_avg, bye, kickoff, started`.
- `warnings[] {level: alert|warning|info, text}`.
- `free_agents[]`. For now the list holds the players with the highest ownership.
- `pending[]`. This list names the checks that the program does not have yet: best lineup, win probability and free-agent scoring.

The panel must show `pending`. Then nobody mistakes "no warnings" for "the lineup is optimal".

---

## 1. Background and goal

- I play NFL fantasy football on ESPN in **two private leagues** (the same ESPN account) in the 2026 season. The program must handle one or more leagues.
- Later (the background phase, see section 0) I want a **lightweight background program** on my Google Cloud VM.
  It checks the leagues on a schedule.
  It **notifies me only when I need to act**. It makes no other noise.
  Sections 6, 7 (background use), 8 and 13 describe it. They are **paused** until the extension works.
- The design is the same as in my **stock-ai** project.
  A scheduled job starts a free "gatekeeper" check.
  The flow continues only when something new happened.
  Then an LLM writes an explanation, and the program sends a push notification.
  Reuse the code structure of stock-ai and its config, logging and notifier conventions.
  **Read its code first**: `/Users/rick/Desktop/Projects/stock-ai-`.
- I come from Java and I am not fluent in Python. Explain your design choices in some detail. Reply to me in Chinese. Write code comments in English.
- This is an **advisory tool**. It only reads from ESPN.
  It never changes my lineup. It never adds or drops players. It never proposes trades on its own.

---

## 2. Scope

### v1 (build this first)
1. **Lineup alerts.**
   Push "start X, bench Y" when one of these cases occurs.
   A starter is OUT or on a bye. A slot is empty. An injury status changed. A clearly better lineup exists.
   Include the win probability before and after the change.
2. **Free-agent alerts.**
   Push a message when a pickup clearly improves my roster. Say who to add and who to drop.
   Flag players that other teams dropped recently. Flag players whose ownership rises.
3. **Health alerts** (see section 6.3): the cookie expired, the ESPN schema changed, and a weekly heartbeat.
4. **AI explanation** (optional). Use my own API key to turn the computed results into short, plain advice. Without a key, use templates.

### v2 (do NOT build it yet, but keep the design open for it)
- **Trade suggestions** (section 5.6).
- A weekly matchup preview with the opponent, the projected score and the win probability. Also an "all good, X% win probability" message before the Sunday kickoff.
- FAAB bid suggestions, when the league uses FAAB.

There is no multi-user support. The only UI is the Chrome side panel (section 0).

---

## 3. Tech stack

- Python 3.10 or newer. The Docker image and CI use 3.12.
  Keep the dependencies minimal: `requests`, `python-dotenv` and `loguru` (logging, as in stock-ai).
  Call ESPN with `requests` directly. Always use a timeout and retries.
  The `espn_api` library sets no request timeouts. Use it only as a reference and copy its constant tables.
- Use SQLite (the standard `sqlite3` module) for state and de-duplication.
- Deployment uses a **Compute Engine VM** with **Docker Compose**, as stock-ai does (see section 13). Use no Cloud Run and no systemd.
- Store and compare all timestamps in UTC with a time zone. Convert to local time only to display a time and to decide the quiet hours.

---

## 4. ESPN data (an unofficial API that can change at any time)

**League endpoint**: `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}`

A private league needs two cookies: `espn_s2` and `SWID`.
A 401 means that the cookies expired or are wrong.
Raise a clear error **and send a health alert** (section 6.3).

| Purpose | Request | Key fields |
|---|---|---|
| League data | `?view=mSettings&view=mTeam&view=mRoster&view=mMatchupScore` | `scoringPeriodId` (current week), `status.currentMatchupPeriod`, `settings.rosterSettings.lineupSlotCounts`, `settings.tradeSettings.deadlineDate`, `teams[].roster.entries[]` (`lineupSlotId`, `playerPoolEntry.player`), `members[]`, `schedule[]` |
| NFL schedule | `.../games/ffl/seasons/{year}?view=proTeamSchedules_wl` | `settings.proTeams[].proGamesByScoringPeriod[week]`. No entry means a bye. `date` is the kickoff time (a timestamp in milliseconds). |
| Free agents | league endpoint `?view=kona_player_info&scoringPeriodId={week}`, header `x-fantasy-filter: {"players":{"filterStatus":{"value":["FREEAGENT","WAIVERS"]},"limit":100,"sortPercOwned":{"sortPriority":1,"sortAsc":false}}}` | `players[].status` (WAIVERS or FREEAGENT), `player.ownership.percentOwned` and `percentChange` |
| Weekly score history | league endpoint `?view=kona_playercard`, header `{"players":{"filterIds":{"value":[ids]},"filterStatsForTopScoringPeriodIds":{"value":week,"additionalValue":["00{year}","10{year}"]}}}`, at most 40 ids per request | `player.stats[]` |
| Recently dropped | league endpoint plus `/communication/?view=kona_league_communication`, with the filter set to `ACTIVITY_TRANSACTIONS` | `messageTypeId` 179, 181 and 239 mean DROPPED. `targetId` is the playerId. |

**How to read `stats[]`**
- `statSourceId`: 0 means actual, 1 means projected.
- `statSplitTypeId`: 0 is the full season, 1 is a single week.
- `scoringPeriodId`: the week number.
- `appliedTotal`: the fantasy points.
- An empty `stats` means that the player did not play that week.

**ID tables**
- `lineupSlotId`: 0 QB, 2 RB, 4 WR, 6 TE, 7 OP, 16 D/ST, 17 K, 20 BE, 21 IR, 23 FLEX (RB, WR or TE). The full table is `POSITION_MAP` in `football/constant.py` of espn_api.
- `defaultPositionId`: 1 QB, 2 RB, 3 WR, 4 TE, 5 K, 16 D/ST.
- `proTeamId` to team abbreviation: use `PRO_TEAM_MAP` from espn_api.

**Several leagues.**
`ESPN_LEAGUE_IDS` holds one or more leagues of the same ESPN account.
The leagues share the cookies.
The program fetches and analyzes each league on its own, with one `EspnClient` for each league.
The NFL schedule is the same for every league, so fetch it once for each check.
The push titles carry the league name.

**My team** (for each league).
My team is the team whose `owners` contain my SWID.
When this detection fails, set the team in `ESPN_TEAM_IDS` (`league_id:team_id`).

**Edge cases that the parser must handle**
- `scoringPeriodId` (the NFL week) and `currentMatchupPeriod` are not always equal. Playoff matchups can last several weeks. Never assume that the two are equal.
- A missing or null projection or stat must not crash the run.
- An unknown `lineupSlotId` or position id must not crash the run. Log a warning and skip it.

**Reference implementation**: [cwendt94/espn-api](https://github.com/cwendt94/espn-api).
Its folder `tests/football/unit/data/` holds real ESPN JSON that works as test fixtures.

One check should send about 6 to 10 requests. Keep the request rate low.

---

## 5. Analysis logic (Python computes every number, and the LLM only explains)

### 5.1 Best lineup for this week
- The starting slots are all slots in `lineupSlotCounts` with a count above 0, except BE and IR.
- Compute the expected points of each player this week:
  - A finished game gives the actual points.
  - A game in progress gives the actual points plus the projected points times the fraction of time left.
  - A game that has not started gives the projected points.
  - A player who is OUT, on IR, suspended or on a bye gets 0.
  - A Doubtful player gets the projected points times a discount factor.
  - A Questionable player gets the projected points times a smaller discount factor.
  - The two discounts are config values (`DOUBTFUL_DISCOUNT`, `QUESTIONABLE_DISCOUNT`). Pick sensible defaults and document them.
- **Locked players.**
  ESPN locks each player at the kickoff of that player.
  A locked player cannot move.
  A locked starter **keeps the current slot**.
  First assign each locked starter to the current slot. Then optimize the remaining slots with the unlocked players.
- The best lineup is a matching with the maximum weight, under the slot eligibility rules.
  Sort the candidate players by expected points, from high to low.
  Try to add each player to the lineup with bipartite augmenting paths (Kuhn's algorithm).
  The result is optimal for any configuration of FLEX, OP and the other slots.
- The output names who to start, who to bench and how many points the change gains.
  It also warns about OUT players, byes and empty slots in the current lineup.

### 5.2 Win probability
- For each team, mu is the sum of the expected points of the starters.
- For each player who has not finished, sigma is about 0.45 x projected + 1.5.
- The win probability is `Phi((muA - muB) / sqrt(sigmaA^2 + sigmaB^2))`.
- The output shows the win probability of the current lineup and the win probability after the change.

### 5.3 Rest-of-season (ROS) value, in points for each week
- The ROS value is a weighted average:
  - this week's projection: 0.40
  - the average of the last 3 games: 0.25
  - the season average: 0.20
  - the ESPN projection for the full season, per game: 0.15
- When an input is missing (for example early in the season), scale the remaining weights so that they sum to 1.
- The injury multiplier is 0.4 for IR (a long-term injury) and 0.85 for OUT.
- The team value TV is the total of the ROS-optimal starting lineup plus 0.2 x the bench value.
- Known limit: the ROS value ignores future bye weeks and injury return dates. Keep this limit visible in the docs.

### 5.4 Free agents
- For each of the top 100 free agents, try to drop each player on my roster. Compute two changes:
  - (a) the change in TV, which is the change in points for each future week
  - (b) the change in the starting lineup of this week
- Recommend a move when one of these holds:
  - The move gains 1.0 point or more for each future week.
  - The move gains 3.0 points or more this week, and the loss for each future week is at most 0.5 point.
- The thresholds are config values.
- The tags are: waiver claim needed or direct add (from `status`), recently dropped, and ownership rising.
- When the league uses FAAB or waiver priority `[CONFIRM: which one?]`, show it in the alert. Bid suggestions are v2.

### 5.5 Players to drop
- Never suggest that I drop a locked player or a player on IR.
  The one exception is a league setting that makes the drop free.
- Prefer the bench player with the lowest TV contribution.

### 5.6 Trades (v2, the spec stays here for later)
- Try 1-for-1 and 2-for-1 trades against every other team. In a 2-for-1 trade I give 2 players and get 1.
  - I fill the roster spot that I free with the best free agent. Then I compute the values again.
  - The extra player on the other team replaces the worst bench player of that team.
- Keep only the trades that raise the TV of both sides. My TV must rise by at least 1.0 and the other TV by at least 0.3.
  The ROS value is a rough estimate, so keep these thresholds conservative.
- Explain each trade. Name the starter of mine that their player would replace. Name the starter of theirs that my player would replace.
- Suggest at most 2 trades for each team and 5 trades in total. Suggest no trades after the trade deadline.
- The search has about 12 teams x C(15,2) x 15, which is about 20 thousand combinations.
  Cache the lineup results. A run should take a few seconds.

---

## 6. Alerts, de-duplication, schedule and health

> **Background phase, paused.** The extension does not use this section. It stays here, so the background program can use `pipeline.analyze` later.

### 6.1 Check flow (the "gatekeeper")
The check runs these steps in order:
1. Fetch the data.
2. Analyze the data.
3. Build the alerts.
4. Compare the alerts with the alerts that SQLite already holds.
5. Send **only the new alerts** to the AI and the notifier.

**De-dup keys**

With several leagues, every league alert key starts with the league id.
An alert about the account (cookie expired, heartbeat) has no league.

| Alert | Key |
|---|---|
| Lineup | league, week and the specific swap |
| Injury | league, player, new status and week |
| Free agent | league, week and player |
| Trade (v2) | league and week |
| Preview (v2) | league and week |

### 6.2 Schedule and quiet hours
- `check` is the single entry point. It decides by itself whether it should run now (`scheduler.should_run_now()`).
  The `run` loop (the Docker `CMD`) can then call it every `CHECK_INTERVAL_SECONDS` (default 600).
- Derive the schedule from the NFL schedule that the program already fetches. Do not use fixed weekdays.
  This covers Thanksgiving, Christmas, Saturday games and London games.
  - **Active window.** The window starts `ACTIVE_LEAD_HOURS` (default 2) before the first kickoff of a game day. It ends 4 hours after the last kickoff. In this window, run every 10 minutes.
    The window should cover the release of the inactive list, about 90 minutes before the kickoff.
  - **Outside the window**, run every 60 minutes.
- **Quiet hours** (default 23:00 to 08:00 local time). Hold non-urgent alerts until the quiet hours end.
  A lineup problem for a game that starts within a few hours is urgent. Send it anyway.
- The time zone comes from `TIMEZONE`. Everything inside the program stays in UTC.

### 6.3 Health alerts (a silent failure is the biggest risk)
- **401 or cookie expired.** Send one push: "ESPN cookie expired, update `ESPN_S2` and `SWID`". Use de-duplication, so the push does not repeat in every run.
- **Parse or schema failure.** When the ESPN response no longer matches what the parser expects, send a push and log the details. Do not only log it.
- **Heartbeat.** Once a week, send "still alive, last successful check at ...". You can also send it after each successful Sunday window.
  You can also ping a healthchecks.io URL (`HEALTHCHECK_URL`) after each successful run.
- **All notification channels fail.** Log an error and leave the alerts unmarked. The next check then retries them.
  Docker restarts a crashed container (`restart: unless-stopped`).

---

## 7. AI (optional, my own key)

- **In the extension (now).**
  The program calls the AI only when I press "Explain with AI".
  The panel sends the key, the provider and the model with each request (`/explain`).
  `AI_*` in `.env` is only a fallback.
  `ffai/ai.py` implements this.
  The request holds only the basic fields: model, max_tokens, system and messages.
  For OpenAI-compatible services the request has no `max_tokens`, because newer OpenAI models renamed it.
- **In the background program (later).** The program calls the AI only when new alerts exist.
- Without a key, use the template text.
- The code supports two interfaces. Both use plain HTTP and no SDK:
  - **Anthropic Messages API.** `POST https://api.anthropic.com/v1/messages` with the headers `x-api-key` and `anthropic-version: 2023-06-01`. The default model is `claude-sonnet-5-5`.
    Newer models can reject `temperature` and `top_p`, so do not send them.
    `output_config.effort = "low"` can save cost.
    **Check the official docs for the exact parameters before you rely on this.**
  - **OpenAI-compatible services** (OpenAI, DeepSeek, Gemini, OpenRouter and others). `POST {AI_BASE_URL}/chat/completions` with the header `Authorization: Bearer`.
- The prompt passes the computed data as JSON. It tells the model to:
  - write in Chinese, in a short form that suits a phone notification
  - put the most urgent action first and give one reason for each recommendation
  - invent no injury news and copy the numbers exactly
- When the AI call fails, fall back to the template text. **An AI failure must never block the notification.**

---

## 8. Notifications

> **Background phase, paused.** The extension shows the results in the panel. The program pushes and emails nothing for now.

- Send each message to every channel that `.env` configures. Several channels can be active at once.
  - Email: Gmail SMTP with an app password, as in stock-ai.
  - ntfy: a phone push. Publish as JSON, so Chinese text displays correctly. Use a long random string as the topic name.
  - A Telegram bot.
  - A Discord webhook.
- The program only logs a failure in one channel. The failure does not crash the program.
- When **all** channels fail, do not mark the alert as sent. The next check then retries it.

---

## 9. Configuration (.env)

In the extension phase, only the service settings below matter, and `.env` is optional.
The extension sends the league ids, the SWID and the AI settings with each request.
The ESPN cookie and the notification settings belong to the background phase.

```
SERVICE_PORT=8765        # The service for the extension. It always listens on 127.0.0.1.
EXTENSION_ID=            # Optional. The service accepts only this extension id.
ESPN_LEAGUE_IDS=         # Background phase. One or more ids, separated by commas.
ESPN_YEAR=2026
ESPN_S2=                 # Background phase only. All leagues share it, because the cookies belong to the account.
ESPN_SWID=
ESPN_TEAM_IDS=           # Optional, for each league ("1669256142:16"). The program detects the team from the SWID when this is empty.
TIMEZONE=America/Denver
QUIET_HOURS=23-8
ACTIVE_LEAD_HOURS=2
DOUBTFUL_DISCOUNT=
QUESTIONABLE_DISCOUNT=
# Thresholds: LINEUP_MIN_GAIN, FA_MIN_GAIN, FA_MIN_WEEK_GAIN
# v2: TRADE_MIN_GAIN, TRADE_MIN_PARTNER_GAIN
AI_PROVIDER=anthropic    # "anthropic" or "openai"
AI_API_KEY=
AI_MODEL=
AI_BASE_URL=
AI_EFFORT=low
EMAIL_FROM= / EMAIL_PASSWORD= / EMAIL_TO=
NTFY_TOPIC=
TELEGRAM_BOT_TOKEN= / TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
HEALTHCHECK_URL=         # Optional.
```

`espn_s2` is effectively my ESPN login credential.
Set the permissions of `.env` to 600, add `.env` to `.gitignore`, and never print the value in logs.

---

## 10. Command line

| Command | Purpose |
|---|---|
| `python -m ffai check [--dry-run]` | Run one check. The command decides by itself whether it is time to run (see 6.2). `--dry-run` only prints the messages. It sends no push, records nothing and ignores the schedule gate. |
| `python -m ffai serve [--port]` | Run the local service that the Chrome extension talks to. It listens on 127.0.0.1 only. The default port is 8765. |
| `python -m ffai run` | Loop forever and call `check` every `CHECK_INTERVAL_SECONDS`. Docker runs this command (`CMD`). |
| `python -m ffai report` | Print the full analysis in the terminal: lineup, win probability, free agents and the matchups of the whole league. |
| `python -m ffai teams` | List all teams and their ids. |
| `python -m ffai test-notify` | Send a test message to every configured channel. |
| `python -m ffai demo` | Run on built-in fake data. It needs no ESPN connection. |

---

## 11. Suggested project structure

```
fantasy-analysis/
├── ffai/
│   ├── config.py        # load .env into a settings object
│   ├── log_config.py    # loguru setup
│   ├── retry_util.py    # retry with backoff
│   ├── espn_client.py   # HTTP with timeout and retry
│   ├── parser.py        # raw JSON to dataclasses (pure, testable)
│   ├── models.py
│   ├── lineup.py        # slot matching optimizer
│   ├── analysis.py      # win probability, ROS, free agents (trades in v2)
│   ├── alerts.py        # build alerts, de-dup keys and health alerts
│   ├── store.py         # SQLite
│   ├── ai.py            # Anthropic and OpenAI-compatible
│   ├── notify.py        # email, ntfy, telegram, discord
│   ├── scheduler.py     # schedule (from the NFL schedule) and quiet hours (background phase)
│   ├── constants.py     # ESPN slot and position id tables
│   ├── pipeline.py      # analyze(payload): the one entry point for analysis
│   ├── service.py       # local HTTP service for the extension
│   └── cli.py
├── extension/           # Chrome MV3 side panel (plain JS, no build step)
├── tests/
├── .github/workflows/ci.yml
├── Dockerfile, docker-compose.yml, DEPLOY.md
├── requirements.txt, requirements-dev.txt
├── .env.example
└── README.md            # written in Chinese
```

---

## 12. Testing

- Write unit tests with fake data for the lineup optimizer (including locked starters that occupy slots), the win probability and the free-agent logic. The trade tests come with v2.
- Test the parser against the real JSON in the espn-api repository. Include missing and null projections.
- Test the schedule logic against Thanksgiving, a Saturday game day and a London early game.
- Run `report` and `check --dry-run` locally against my real league. Confirm that the results look sensible **before you deploy**.

---

## 13. Deployment (the background phase, on the same GCP VM as stock-ai)

> **Paused.** The extension runs on my laptop (`python -m ffai serve`). The current phase deploys nothing. The deploy files are ready, so the background phase later needs only "clone and `up -d`".

- **The same server as stock-ai.**
  stock-ai runs on one e2-micro VM (name `stock-ai`, zone `us-west1-a`, 1 GB of RAM plus swap).
  It runs as a Docker Compose project cloned at `~/stock-ai-`.
  Its containers are `stock-ai-monitor` and `stock-ai-api`. The API listens on `127.0.0.1:8000` only.
  ffai goes on that VM as **its own repo and its own Compose project** (`~/fantasy-analysis`, container `ffai-monitor`).
  ffai is not part of the compose file or the process of stock-ai.
  A crash or an out-of-memory error in one project therefore cannot stop the other project.
  Never edit the repo of stock-ai.
- **Docker Compose**, as in stock-ai (see `DEPLOY.md`).
  The container runs `python -m ffai run`. `check` decides by itself whether it is time to work.
  The state lives in `./data/ffai.db` (a volume).
  Read the logs with `docker compose logs -f`.
  `restart: unless-stopped` restarts the container after a crash.
  `mem_limit: 256m` protects stock-ai on the 1 GB VM.
- The program makes outbound requests only. It publishes **no ports**, because stock-ai uses port 8000. No firewall port needs to open.
- **A later option (not built).** Run `ffai serve` on the VM and bind it to `127.0.0.1`. Reach it over an SSH tunnel, as with the dashboard of stock-ai. The extension then does not need a local Python process.
- **Deploy early** once the background program exists. Let it run through at least one real Sunday. Lineup alerts depend on real-game behavior (inactive lists, ESPN status lag). A local dry run cannot show that behavior.

---

## 14. Build order

Each step must run on its own before the next step starts. A step marked (done) exists in the code.

1. (done) Read the code of stock-ai and follow its structure. Scaffold the package.
2. (done) The parser and `pipeline.analyze` against real espn-api fixtures. The local service (`serve`). The Chrome side panel with the Analyze and Explain-with-AI buttons.
3. **Spike on my real ESPN login.** Load the unpacked extension and click Analyze. Confirm that the ESPN API accepts the cookies of the browser. When ESPN answers 401, switch to a content script on `fantasy.espn.com` before you build more.
4. The lineup optimizer and the win probability. Plug them into `pipeline.analyze` and show them in the panel.
5. Free agents. Plug them in the same way.
6. The background phase, after I understand the cookie behavior. `EspnClient` and the cookie feed the same `analyze`. Then add de-dup, notifications, the scheduler and health alerts. Then deploy on the stock-ai VM (section 13).
7. v2: trades, the weekly preview and FAAB suggestions.

---

## 15. Open questions

- Which notification channel do I mainly use (ntfy, Telegram or email)?
- Does the league use FAAB or waiver priority? What are the day and time of waiver processing?
- What is the id of my second league? The first league is 1669256142, and my team id there is 16.
