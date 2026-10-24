# Deploy (GCP Compute Engine VM, Docker Compose)

Same approach as stock-ai. The program only makes outbound requests, so no firewall port needs to be opened.

## First time
1. Install Docker and the Compose plugin on the VM.
2. Clone the repo and `cd fantasy-analysis`.
3. Create `.env` from `.env.example` and fill in the ESPN and channel settings. Keep the file out of git. Then `chmod 600 .env`.
4. Check the channels before starting: `docker compose run --rm ffai python -m ffai test-notify`.
5. Start it: `docker compose up -d --build`.

## Update
```
cd fantasy-analysis && git pull && docker compose up -d --build
```

## Look at it
- Logs: `docker compose logs -f ffai`
- State: SQLite file in `./data/ffai.db` (survives rebuilds).

## Notes
- The container runs `python -m ffai run`. It wakes every `CHECK_INTERVAL_SECONDS` (default 600) and `check` decides by itself whether there is work (SPEC 6.2).
- If ESPN logs you out, the program sends one "cookie expired" alert. Copy fresh `espn_s2` and `SWID` values into `.env` and run `docker compose up -d` again.
- Deploy only after SPEC build step 5 works, and let it run through one real Sunday before building more.
