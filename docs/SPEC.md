# fantasy-analysis: ESPN Fantasy lineup / free-agent / trade alert assistant

> Project brief for Claude Code. Items marked `[CONFIRM]` need to be checked with me before you build them.

---

## 0. Architecture: Chrome extension + local service first, background later

**Current phase.** The first front end is a **Chrome extension** (side panel). It runs analysis **only when I press a button**. There is no always-on background run and no email for now. The background part comes back after I understand how ESPN's login cookie behaves (it expires, and handling it is awkward).

```
Chrome extension (side panel)                 local service (Python, 127.0.0.1:8765)
  fetch ESPN with my browser login  ──raw JSON──>  ffai.pipeline.analyze(payload)
  render the result                 <──result────      parse -> my team -> checks (lineup, win%, free agents later)
                                                               ^
future background `check` (cookie via EspnClient) ─────────────┘  same analyze()
```

- **No cookie handling in the extension.** I am already logged in to ESPN in Chrome. The extension (host permission for `*.espn.com`) calls ESPN's API and the browser attaches the cookies. `espn_s2` is never read, stored or sent. The one value it reads is `SWID` (it identifies me and finds my team; it is not a login credential). If ESPN answers 401, the panel says "log in to ESPN".
- **One analysis codebase.** `ffai/pipeline.py: analyze(payload) -> dict` takes raw ESPN JSON and returns JSON-friendly data. The extension feeds it today; the background `check` can feed it later with `EspnClient`. Nothing in `lineup.py` / `analysis.py` knows where the data came from.
- **Analysis runs on a button press.** Opening the panel makes no ESPN request (only a local ping to see if the service is up). "Explain with AI" is a second, separate button, so LLM cost is always my choice.
- **AI settings live in the panel** (provider, API key, model, base URL). The key is stored in `chrome.storage.local` (not encrypted by Chrome), sent only to `127.0.0.1`, and from there to the AI provider. The service never stores or logs it. `AI_*` in `.env` is only a fallback.
- **The background part will run on the same VM as stock-ai**: its own repo and its own Docker Compose project next to stock-ai's, not inside stock-ai's compose file or process (section 13).

### Local service API (`python -m ffai serve`, loopback only)

| Route | Request body | Answer |
|---|---|---|
| `GET /health` | - | `{"ok": true}` |
| `POST /analyze` | `{"league": <ESPN league JSON, views mSettings+mTeam+mRoster+mMatchupScore>, "pro_schedule": <proTeamSchedules_wl JSON>, "free_agents": <kona_player_info JSON, optional>, "swid": "{...}", "team_id": "16" (optional)}` | the analysis result (below) |
| `POST /explain` | `{"result": <an /analyze result>, "ai": {"provider": "anthropic"\|"openai", "api_key", "model", "base_url"}}` | `{"text", "source": "ai"\|"template", "error"}` |

Errors: `422` with `kind: "parse"` for an ESPN format problem or an unknown SWID, `400` bad JSON, `413` body over 16 MB, `415` wrong content type, `403` wrong Host or Origin, `500` internal (details only in the service log). Only `chrome-extension://` origins are accepted (pin one with `EXTENSION_ID`).

**Analysis result** (`/analyze`): `league {id, name, year, week}`, `team {id, name}`, `starters[]` / `bench[]` / `ir[]` (each player: `name, position, pro_team, slot, injury, projected, actual, season_avg, bye, kickoff, started`), `warnings[] {level: alert|warning|info, text}`, `free_agents[]` (top by ownership for now), `pending[]` (checks not written yet: best lineup, win probability, free-agent scoring). The panel must show `pending`, so nobody mistakes "no warnings" for "lineup is optimal".

---

## 1. Background and goal

- I play NFL fantasy football on ESPN in **two private leagues** (same ESPN account), 2026 season. The program must handle one or more leagues.
- Later (background phase, see section 0) I want a **lightweight background program** running on my Google Cloud VM. It checks the league on a schedule and **only notifies me when I need to act**. No noise otherwise. Sections 6, 7 (background use), 8 and 13 describe it and are **paused** until the extension works.
- Same design as my **stock-ai** project: scheduled job -> free "gatekeeper" check (continue only if something new happened) -> LLM explanation -> push notification. Reuse stock-ai's code structure and its config, logging and notifier conventions. **Read its code first**: `/Users/rick/Desktop/Projects/stock-ai-`.
- I come from Java and I'm not fluent in Python. Explain your design choices in some detail when you talk to me (reply in Chinese). Code comments must be in English.
- This is an **advisory tool**. It only reads from ESPN. It never changes my lineup, never adds/drops players, never proposes trades on its own.

---

## 2. Scope

### v1 (build this first)
1. **Lineup alerts**: push "start X, bench Y" when a starter is OUT / on bye / an empty slot exists / injury status changed / a clearly better lineup exists. Include win probability before and after the change.
2. **Free-agent alerts**: push when picking up a player clearly improves my roster. Say who to add and who to drop. Flag recently dropped players and players whose ownership is rising.
3. **Health alerts** (see section 6.3): cookie expired, ESPN schema changed, weekly heartbeat.
4. **AI explanation** (optional): use my own API key to turn the computed results into short, plain-language advice. Fall back to templates without a key.

### v2 (do NOT build yet, design the code so it can be added)
- **Trade suggestions** (section 5.6).
- Weekly matchup preview: opponent, projected score, win probability. Also an "all good, X% win probability" message before Sunday kickoff.
- FAAB bid suggestions (if the league uses FAAB).

No multi-user support. The only UI is the Chrome side panel (section 0).

---

## 3. Tech stack

- Python 3.10+ (Docker image and CI use 3.12), minimal dependencies: `requests`, `python-dotenv`, `loguru` (logging, same as stock-ai). Call ESPN with `requests` directly, always with a timeout and retries. The `espn_api` library does not set request timeouts, so use it only as a reference (copy its constant tables).
- SQLite (stdlib `sqlite3`) for state and de-duplication.
- Deployment: **Compute Engine VM** with **Docker Compose**, same as stock-ai (see section 13). No Cloud Run, no systemd.
- Store and compare all timestamps in UTC (timezone-aware). Convert to local time only for display and quiet hours.

---

## 4. ESPN data (unofficial API, can change at any time)

**League endpoint**: `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}`

A private league needs two cookies: `espn_s2` and `SWID`. A 401 means the cookies are expired or wrong. Raise a clear error **and send a health alert** (section 6.3).

| Purpose | Request | Key fields |
|---|---|---|
| League data | `?view=mSettings&view=mTeam&view=mRoster&view=mMatchupScore` | `scoringPeriodId` (current week), `status.currentMatchupPeriod`, `settings.rosterSettings.lineupSlotCounts`, `settings.tradeSettings.deadlineDate`, `teams[].roster.entries[]` (`lineupSlotId`, `playerPoolEntry.player`), `members[]`, `schedule[]` |
| NFL schedule | `.../games/ffl/seasons/{year}?view=proTeamSchedules_wl` | `settings.proTeams[].proGamesByScoringPeriod[week]`: no entry means bye; `date` is kickoff time (ms timestamp) |
| Free agents | league endpoint `?view=kona_player_info&scoringPeriodId={week}`, header `x-fantasy-filter: {"players":{"filterStatus":{"value":["FREEAGENT","WAIVERS"]},"limit":100,"sortPercOwned":{"sortPriority":1,"sortAsc":false}}}` | `players[].status` (WAIVERS / FREEAGENT), `player.ownership.percentOwned / percentChange` |
| Weekly score history | league endpoint `?view=kona_playercard`, header `{"players":{"filterIds":{"value":[ids]},"filterStatsForTopScoringPeriodIds":{"value":week,"additionalValue":["00{year}","10{year}"]}}}`, at most 40 ids per request | `player.stats[]` |
| Recently dropped | league endpoint + `/communication/?view=kona_league_communication`, filter set to `ACTIVITY_TRANSACTIONS` | `messageTypeId` 179 / 181 / 239 = DROPPED, `targetId` = playerId |

**Reading `stats[]`**
- `statSourceId`: 0 = actual, 1 = projected
- `statSplitTypeId`: 0 = full season, 1 = single week
- `scoringPeriodId`: week number
- `appliedTotal`: fantasy points
- empty `stats`: did not play that week

**ID tables**
- `lineupSlotId`: 0 QB, 2 RB, 4 WR, 6 TE, 7 OP, 16 D/ST, 17 K, 20 BE, 21 IR, 23 FLEX (RB/WR/TE). Full table: `POSITION_MAP` in espn_api's `football/constant.py`.
- `defaultPositionId`: 1 QB, 2 RB, 3 WR, 4 TE, 5 K, 16 D/ST
- `proTeamId` -> team abbreviation: `PRO_TEAM_MAP` from espn_api.

**Several leagues**: `ESPN_LEAGUE_IDS` holds one or more leagues from the same ESPN account. The cookies are shared. Each league is fetched and analyzed on its own, one `EspnClient` per league. The NFL schedule is the same for every league, so fetch it once per check. Push titles carry the league name.

**My team** (per league): the team whose `owners` contains my SWID, or set it in `ESPN_TEAM_IDS` (`league_id:team_id`) when detection fails.

**Edge cases to handle in the parser**
- `scoringPeriodId` (NFL week) and `currentMatchupPeriod` are not always 1:1 (multi-week playoff matchups). Never assume they are equal.
- Missing or null projections and stats must not crash the run.
- Unknown `lineupSlotId` / position IDs: log a warning and skip, do not crash.

**Reference implementation**: [cwendt94/espn-api](https://github.com/cwendt94/espn-api). Its `tests/football/unit/data/` has real ESPN JSON usable as test fixtures.

A single check should issue roughly 6-10 requests. Keep the request rate low.

---

## 5. Analysis logic (Python computes every number; the LLM only explains)

### 5.1 Best lineup for this week
- Starting slots: every slot in `lineupSlotCounts` with count > 0, except BE and IR.
- Expected points per player this week:
  - game finished: actual points
  - game in progress: actual + projected x remaining-time fraction
  - not started: projected points
  - OUT, IR, suspended, bye: 0
  - Doubtful: projected x a discount factor
  - Questionable: projected x a smaller discount factor
  - Both discounts are config values (`DOUBTFUL_DISCOUNT`, `QUESTIONABLE_DISCOUNT`); pick sensible defaults and document them.
- **Locked players**: ESPN locks each player at his own kickoff. A locked player cannot move, and a locked starter **keeps occupying his current slot**. Pre-assign locked starters to their slots first, then optimize the remaining slots with the unlocked players.
- Optimal lineup = maximum-weight matching with slot eligibility. Sort the candidate players by expected points, descending, and try to add each one to the lineup using bipartite augmenting paths (Kuhn's algorithm). This is optimal regardless of how FLEX/OP/etc. are configured.
- Output: who to start, who to bench, how many points gained, plus warnings for OUT / bye / empty slots in the current lineup.

### 5.2 Win probability
- Per team, mu = sum of expected points of the starters.
- For each player who has not finished, sigma ~= 0.45 x projected + 1.5.
- Win probability = Phi((muA - muB) / sqrt(sigmaA^2 + sigmaB^2)).
- Output "current lineup win probability -> after the change".

### 5.3 Rest-of-season (ROS) value, per-week points
- Weighted average: this week's projection 0.40, last-3-games average 0.25, season average 0.20, ESPN full-season projection per game 0.15. If an input is missing (e.g. early in the season), re-normalize the remaining weights.
- Injury multiplier: IR (long-term) x 0.4, OUT x 0.85.
- Team value TV = total of the ROS-optimal starting lineup + 0.2 x bench value.
- Known limitation: ROS ignores future bye weeks and injury return dates. Keep that limitation visible in the docs.

### 5.4 Free agents
- For each of the top 100 free agents, try dropping each player on my roster and compute: (a) the change in TV (points per week going forward), and (b) the change in this week's starting lineup.
- Recommend when either holds:
  - going forward: +1.0 point/week or more
  - this week: +3.0 points or more, and the going-forward loss is at most 0.5 point/week
  - Thresholds are config values.
- Tags: needs waiver claim vs. can add directly (`status`), recently dropped, ownership rising.
- If the league uses FAAB or waiver priority `[CONFIRM: which one?]`, show it in the alert. (Bid suggestions are v2.)

### 5.5 Dropping candidates
- Never suggest dropping a player who is locked or on IR unless the league settings make it free to do so. Prefer the lowest-TV-contribution bench player.

### 5.6 Trades (v2, spec kept here for later)
- Against every other team, try 1-for-1 and 2-for-1 (I give 2, get 1).
  - The roster spot I free up is filled with the best free agent before recomputing.
  - The extra player on their side replaces their worst bench player.
- Keep only trades where both sides' TV improves: me at least +1.0, them at least +0.3. Because ROS is a rough estimate, keep these thresholds conservative.
- Explain each trade: which of my starters their player would replace, and which of theirs mine would replace.
- At most 2 per team, top 5 overall. No suggestions after the trade deadline.
- About 12 teams x C(15,2) x 15 ~= 20k combinations. Cache lineup results; a run should take a few seconds.

---

## 6. Alerts, de-duplication, cadence and health

> **Background phase - paused.** Not used by the extension. Kept so the background part can be built later on top of `pipeline.analyze`.

### 6.1 Check flow (the "gatekeeper")
Fetch data -> analyze -> build alerts -> compare with alerts already stored in SQLite -> **only new alerts** go to the AI and the notifier.

**De-dup keys**

With several leagues, every league alert key starts with the league id. Health alerts about the account (cookie expired, heartbeat) have no league.

| Alert | Key |
|---|---|
| Lineup | league + week + the specific swap |
| Injury | league + player + new status + week |
| Free agent | league + week + player |
| Trade (v2) | league + week |
| Preview (v2) | league + week |

### 6.2 Cadence and quiet hours
- `check` is the single entry point. It decides by itself whether it should run now (`scheduler.should_run_now()`), so the `run` loop (the Docker `CMD`) can simply call it every `CHECK_INTERVAL_SECONDS` (default 600).
- Derive the schedule from the NFL schedule you already fetch, not from hard-coded weekdays (this covers Thanksgiving, Christmas, Saturday games, London games):
  - **Active window**: from `ACTIVE_LEAD_HOURS` (default 2) before the first kickoff of a game day until the last kickoff + 4 hours -> run every 10 minutes. This should cover the roughly 90-minute-before-kickoff inactive-list release.
  - **Otherwise**: run every 60 minutes.
- **Quiet hours** (default local time 23:00-08:00): hold non-urgent alerts until the window ends. Lineup problems for games starting within a few hours are urgent and are sent anyway.
- Local time zone comes from `TIMEZONE`; everything internal stays in UTC.

### 6.3 Health alerts (silent failure is the biggest risk)
- **401 / cookie expired**: send one push "ESPN cookie expired, update `ESPN_S2`/`SWID`", de-duplicated so it does not repeat every run.
- **Parse or schema failure**: if ESPN's response no longer matches what the parser expects, send a push and log the details. Do not just log it.
- **Heartbeat**: once a week (and optionally after each successful Sunday window) send "still alive, last successful check at ...". Optionally also ping a healthchecks.io URL (`HEALTHCHECK_URL`) after each successful run.
- If all notification channels fail, log an error and leave the alerts unmarked so the next check retries them. A crashed container is restarted by Docker (`restart: unless-stopped`).

---

## 7. AI (optional, my own key)

- **Extension (now):** called only when I press "Explain with AI". The key, provider and model come from the panel with each request (`/explain`); `AI_*` in `.env` is only a fallback. Implemented in `ffai/ai.py`. Only the basic request fields are sent (model, max_tokens, system, messages), and for OpenAI-compatible services no `max_tokens`, because newer OpenAI models renamed it.
- **Background (later):** call it only when there are new alerts.
- Without a key, use template text.
- Support two interfaces, both via plain HTTP, no SDK:
  - **Anthropic Messages API**: `POST https://api.anthropic.com/v1/messages`, headers `x-api-key` and `anthropic-version: 2023-06-01`. Default model `claude-sonnet-5-5`. Newer models may reject `temperature` / `top_p`, so do not send them. `output_config.effort = "low"` can save cost. **Check the official docs for exact parameters before relying on this.**
  - **OpenAI-compatible** (OpenAI / DeepSeek / Gemini / OpenRouter ...): `POST {AI_BASE_URL}/chat/completions`, header `Authorization: Bearer`.
- Prompt: pass the computed data as JSON and instruct the model to:
  - write in Chinese, short, suitable for a phone notification
  - lead with the most urgent action, one reason per recommendation
  - not invent injury news, copy numbers exactly
- If the AI call fails, fall back to template text. **An AI failure must never block the notification.**

---

## 8. Notifications

> **Background phase - paused.** The extension shows results in the panel; nothing is pushed or emailed for now.

- Channels: send to every channel that is configured in `.env`; several can be active at once.
  - Email: Gmail SMTP with an app password, same as stock-ai
  - ntfy: phone push. Publish as JSON so Chinese text renders correctly; use a long random string as the topic name
  - Telegram bot
  - Discord webhook
- A failure in one channel is logged only and does not crash the program. If **all** channels fail, do not mark the alert as sent so it is retried on the next check.

---

## 9. Configuration (.env)

Extension phase: only the service settings below matter, and `.env` is optional (the extension sends the league ids, the SWID and the AI settings with each request). The ESPN cookie and notification settings are for the background phase.

```
SERVICE_PORT=8765        # local service for the extension (always bound to 127.0.0.1)
EXTENSION_ID=            # optional: accept only this extension id
ESPN_LEAGUE_IDS=         # background phase: one or more, comma separated
ESPN_YEAR=2026
ESPN_S2=                 # background phase only; shared by every league (the cookies belong to the account)
ESPN_SWID=
ESPN_TEAM_IDS=           # optional, per league ("1669256142:16"); auto-detected from SWID if empty
TIMEZONE=America/Denver
QUIET_HOURS=23-8
ACTIVE_LEAD_HOURS=2
DOUBTFUL_DISCOUNT=
QUESTIONABLE_DISCOUNT=
# Thresholds: LINEUP_MIN_GAIN / FA_MIN_GAIN / FA_MIN_WEEK_GAIN
# v2: TRADE_MIN_GAIN / TRADE_MIN_PARTNER_GAIN
AI_PROVIDER=anthropic    # or openai
AI_API_KEY=
AI_MODEL=
AI_BASE_URL=
AI_EFFORT=low
EMAIL_FROM= / EMAIL_PASSWORD= / EMAIL_TO=
NTFY_TOPIC=
TELEGRAM_BOT_TOKEN= / TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
HEALTHCHECK_URL=         # optional
```

`espn_s2` is effectively my ESPN login credential: set `.env` permissions to 600, add it to `.gitignore`, and never print it in logs.

---

## 10. Command line

| Command | Purpose |
|---|---|
| `python -m ffai check [--dry-run]` | Run one check (decides itself whether it is time to run, see 6.2). `--dry-run` prints messages only: no push, nothing recorded, and it ignores the schedule gate |
| `python -m ffai serve [--port]` | Run the local service the Chrome extension talks to (127.0.0.1 only, default port 8765) |
| `python -m ffai run` | Loop forever, calling `check` every `CHECK_INTERVAL_SECONDS`. This is the Docker `CMD` |
| `python -m ffai report` | Print the full analysis to the terminal: lineup, win probability, free agents, whole-league matchups |
| `python -m ffai teams` | List all teams and their IDs |
| `python -m ffai test-notify` | Send a test message to every configured channel |
| `python -m ffai demo` | Run on built-in fake data, no ESPN connection needed |

---

## 11. Suggested project structure

```
fantasy-analysis/
├── ffai/
│   ├── config.py        # load .env into a settings object
│   ├── log_config.py    # loguru setup
│   ├── retry_util.py    # retry with backoff
│   ├── espn_client.py   # HTTP + timeout/retry
│   ├── parser.py        # raw JSON -> dataclasses (pure, testable)
│   ├── models.py
│   ├── lineup.py        # slot matching optimizer
│   ├── analysis.py      # win prob, ROS, free agents (trades in v2)
│   ├── alerts.py        # build alerts + dedupe keys + health alerts
│   ├── store.py         # SQLite
│   ├── ai.py            # Anthropic / OpenAI-compatible
│   ├── notify.py        # email / ntfy / telegram / discord
│   ├── scheduler.py     # cadence (from NFL schedule) + quiet hours (background phase)
│   ├── constants.py     # ESPN slot / position id tables
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

- Unit tests with fake data for: lineup optimizer (including locked starters occupying slots), win probability, free-agent logic. Trade tests come with v2.
- Test the parser against the real JSON in the espn-api repository, including missing/null projections.
- Test the cadence logic against Thanksgiving, a Saturday game day and a London early game.
- Run `report` and `check --dry-run` locally against my real league and confirm the results look sensible **before deploying**.

---

## 13. Deployment (background phase: the same GCP VM as stock-ai)

> **Paused.** The extension runs on my laptop (`python -m ffai serve`). Nothing is deployed in the current phase. The deploy files are prepared so the background phase later is "clone and `up -d`".

- **Same server as stock-ai.** stock-ai runs on one e2-micro VM (name `stock-ai`, zone `us-west1-a`, 1 GB RAM plus swap) as a Docker Compose project cloned at `~/stock-ai-` (containers `stock-ai-monitor` and `stock-ai-api`, the API published on `127.0.0.1:8000` only). ffai goes on that VM as **its own repo and its own Compose project** (`~/fantasy-analysis`, container `ffai-monitor`). It is not part of stock-ai's compose file or process, so a crash or out-of-memory in one cannot take the other down. We never edit stock-ai's repo.
- **Docker Compose**, same as stock-ai (see `DEPLOY.md`). The container runs `python -m ffai run`; `check` itself decides whether it is time to do work. State lives in `./data/ffai.db` (volume). Logs: `docker compose logs -f`. `restart: unless-stopped` brings it back after a crash. `mem_limit: 256m` protects stock-ai on the 1 GB VM.
- The program only makes outbound requests. It publishes **no ports** (8000 is stock-ai's), and no firewall port needs to be opened.
- **Later option (not built):** run `ffai serve` on the VM bound to `127.0.0.1` and reach it over an SSH tunnel, like stock-ai's dashboard. The extension would then not need a local Python process.
- **Deploy early** once the background part exists: let it run through at least one real Sunday. Lineup alerts depend on real-game behavior (inactive lists, ESPN status lag) that local dry-runs cannot show.

---

## 14. Build order

Each step must run on its own before starting the next. Steps marked (done) exist in the code.

1. (done) Read stock-ai's code and follow its structure; scaffold the package.
2. (done) Parser and `pipeline.analyze` against real espn-api fixtures; local service (`serve`); Chrome side panel with Analyze and Explain-with-AI buttons.
3. **Spike on my real ESPN login:** load the unpacked extension, click Analyze, and confirm ESPN's API accepts the browser's cookies. If ESPN answers 401, switch to a content script on `fantasy.espn.com` before building more.
4. Lineup optimizer + win probability (plug into `pipeline.analyze`, show in the panel).
5. Free agents (same).
6. Background phase, after I understand the cookie behavior: `EspnClient` + cookie feeding the same `analyze`, de-dup + notifications + scheduler + health alerts, then deploy on the stock-ai VM (section 13).
7. v2: trades, weekly preview, FAAB suggestions.

---

## 15. Open questions

- Which notification channel do I mainly use (ntfy / Telegram / email)?
- Does the league use FAAB or waiver priority? What is the waiver processing day/time?
- What is the id of my second league? (First league: 1669256142, my team id there is 16.)
