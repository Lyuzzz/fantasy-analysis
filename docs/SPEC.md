# fantasy-analysis: ESPN Fantasy lineup / free-agent / trade alert assistant

> Project brief for Claude Code. Items marked `[CONFIRM]` need to be checked with me before you build them.

---

## 1. Background and goal

- I play NFL fantasy football on ESPN in a **private league**, 2026 season.
- I want a **lightweight background program** running on my Google Cloud VM. It checks the league on a schedule and **only notifies me when I need to act**. No noise otherwise.
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

No web UI and no multi-user support.

---

## 3. Tech stack

- Python 3.10+, minimal dependencies: `requests`, `python-dotenv`. Call ESPN with `requests` directly, always with a timeout and retries. The `espn_api` library does not set request timeouts, so use it only as a reference (copy its constant tables).
- SQLite (stdlib `sqlite3`) for state and de-duplication.
- Deployment: **Compute Engine VM**, Linux, **systemd** (see section 13). No Cloud Run.
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

**My team**: the team whose `owners` contains my SWID, or set `ESPN_TEAM_ID` manually.

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

### 6.1 Check flow (the "gatekeeper")
Fetch data -> analyze -> build alerts -> compare with alerts already stored in SQLite -> **only new alerts** go to the AI and the notifier.

**De-dup keys**

| Alert | Key |
|---|---|
| Lineup | week + the specific swap |
| Injury | player + new status + week |
| Free agent | week + player |
| Trade (v2) | week |
| Preview (v2) | week |

### 6.2 Cadence and quiet hours
- `check` is the single entry point. It decides by itself whether it should run now (`scheduler.should_run_now()`), so a systemd timer can simply call it every 10 minutes.
- Derive the schedule from the NFL schedule you already fetch, not from hard-coded weekdays (this covers Thanksgiving, Christmas, Saturday games, London games):
  - **Active window**: from `ACTIVE_LEAD_HOURS` (default 2) before the first kickoff of a game day until the last kickoff + 4 hours -> run every 10 minutes. This should cover the roughly 90-minute-before-kickoff inactive-list release.
  - **Otherwise**: run every 60 minutes.
- **Quiet hours** (default local time 23:00-08:00): hold non-urgent alerts until the window ends. Lineup problems for games starting within a few hours are urgent and are sent anyway.
- Local time zone comes from `TIMEZONE`; everything internal stays in UTC.

### 6.3 Health alerts (silent failure is the biggest risk)
- **401 / cookie expired**: send one push "ESPN cookie expired, update `ESPN_S2`/`SWID`", de-duplicated so it does not repeat every run.
- **Parse or schema failure**: if ESPN's response no longer matches what the parser expects, send a push and log the details. Do not just log it.
- **Heartbeat**: once a week (and optionally after each successful Sunday window) send "still alive, last successful check at ...". Optionally also ping a healthchecks.io URL (`HEALTHCHECK_URL`) after each successful run.
- If all notification channels fail, the run exits non-zero so systemd records the failure.

---

## 7. AI (optional, my own key)

- Call it only when there are new alerts. Without a key, use template text.
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

- Channels: send to every channel that is configured in `.env`; several can be active at once.
  - Email: Gmail SMTP with an app password, same as stock-ai
  - ntfy: phone push. Publish as JSON so Chinese text renders correctly; use a long random string as the topic name
  - Telegram bot
  - Discord webhook
- A failure in one channel is logged only and does not crash the program. If **all** channels fail, do not mark the alert as sent so it is retried on the next check.

---

## 9. Configuration (.env)

```
ESPN_LEAGUE_ID=
ESPN_YEAR=2026
ESPN_S2=
ESPN_SWID=
ESPN_TEAM_ID=            # optional; auto-detected from SWID if empty
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
| `python -m ffai report` | Print the full analysis to the terminal: lineup, win probability, free agents, whole-league matchups |
| `python -m ffai teams` | List all teams and their IDs |
| `python -m ffai test-notify` | Send a test message to every configured channel |
| `python -m ffai demo` | Run on built-in fake data, no ESPN connection needed |

---

## 11. Suggested project structure

```
fantasy-analysis/
├── ffai/
│   ├── config.py        # load .env
│   ├── espn_client.py   # HTTP + timeout/retry
│   ├── parser.py        # raw JSON -> dataclasses (pure, testable)
│   ├── models.py
│   ├── lineup.py        # slot matching optimizer
│   ├── analysis.py      # win prob, ROS, free agents (trades in v2)
│   ├── alerts.py        # build alerts + dedupe keys + health alerts
│   ├── store.py         # SQLite
│   ├── ai.py            # Anthropic / OpenAI-compatible
│   ├── notify.py        # email / ntfy / telegram / discord
│   ├── scheduler.py     # cadence (from NFL schedule) + quiet hours
│   └── cli.py
├── tests/
├── deploy/              # setup_vm.sh, fantasy-analysis.service, fantasy-analysis.timer
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

## 13. Deployment (GCP Compute Engine VM)

- venv for dependencies. A **systemd timer** (every 10 minutes) triggers a oneshot service that runs `python -m ffai check`; `check` itself decides whether it is time to do work. Failures are visible in `journalctl`.
- The program only makes outbound requests, so no firewall ports need to be opened.
- **Deploy early**: as soon as step 5 below works, deploy it and let it run through at least one real Sunday. Lineup alerts depend on real-game behavior (inactive lists, ESPN status lag) that local dry-runs cannot show.

---

## 14. Build order

Each step must run on its own before starting the next:

1. Read stock-ai's code and follow its structure.
2. ESPN client and parser; get `teams` and `report` working on real data.
3. Lineup optimizer + win probability.
4. Free agents.
5. De-dup + notifications + scheduler + health alerts. **Then deploy (section 13).**
6. AI explanations.
7. v2: trades, weekly preview, FAAB suggestions.

---

## 15. Open questions

- Which notification channel do I mainly use (ntfy / Telegram / email)?
- Does the league use FAAB or waiver priority? What is the waiver processing day/time?
- What is my `ESPN_TEAM_ID` (or just rely on SWID auto-detection)?
