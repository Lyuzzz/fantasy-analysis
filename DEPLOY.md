# Deploy (the background phase, on the same VM as stock-ai)

> **Not ready. Do not deploy yet.**
> The background program is paused (SPEC section 0).
> The container runs `python -m ffai run`. This command exits at once, because `check` does not exist yet.
> With `restart: unless-stopped`, Docker would then restart the container in a loop.
> This file and `docker-compose.yml` are ready, so the deploy is quick later.

ffai goes on the **same GCP VM as stock-ai**.
It is its own repo and its own Docker Compose project.
It is not part of the compose file or the process of stock-ai.
A crash or an out-of-memory error in one project therefore cannot stop the other project.
This work changes nothing in the repo of stock-ai.

## What the VM already has (from DEPLOY.md of stock-ai)

| Item | Value |
|---|---|
| VM name | `stock-ai` |
| Zone | `us-west1-a` |
| Size | e2-micro, 1 GB of RAM plus 1 GB of swap |
| Access | The `vmssh` alias, which means `gcloud compute ssh stock-ai --tunnel-through-iap --zone=us-west1-a` |
| Docker, Compose and git | Installed |
| stock-ai | `~/stock-ai-`, with the containers `stock-ai-monitor` and `stock-ai-api` (port `127.0.0.1:8000`) |

So you need **no new VM and no new install**.
The container is `ffai-monitor`. It has a limit of 256 MB and publishes no ports.

## First deploy

1. **Deploy key.**
   Make a second read-only key for this repo on the VM.
   GitHub allows a deploy key on one repo only.
   ```bash
   vmssh
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519_ffai
   cat ~/.ssh/id_ed25519_ffai.pub
   ```
   Add the public key in GitHub: repo **Settings**, then **Deploy keys**. Leave "Allow write access" unchecked.
   Then tell git to use this key for this repo:
   ```bash
   git clone -c core.sshCommand="ssh -i ~/.ssh/id_ed25519_ffai" git@github.com:Lyuzzz/fantasy-analysis.git
   cd fantasy-analysis
   git config core.sshCommand "ssh -i ~/.ssh/id_ed25519_ffai"
   ```
2. **Ship `.env`** from your laptop.
   Git ignores `.env`, so `git pull` does not bring it.
   ```bash
   gcloud compute scp .env stock-ai:~/fantasy-analysis/ --tunnel-through-iap --zone=us-west1-a
   ```
   On the VM, run `chmod 600 ~/fantasy-analysis/.env`.
3. **Start the container.**
   Run `cd ~/fantasy-analysis && docker compose up -d --build`.
4. **Check the memory.**
   The VM is small, so look right after the first start:
   ```bash
   docker stats --no-stream      # ffai-monitor must stay far below 256 MB
   free -m                       # stock-ai must still have room
   ```

## Update

Add an alias next to `vmdeploy` in `~/.zshrc`:

```bash
alias ffdeploy='vmssh --command="cd fantasy-analysis && git pull && docker compose up -d --build"'
```

## Look at the service

- Logs: `docker compose logs -f ffai` (in `~/fantasy-analysis`).
- State: the SQLite file `./data/ffai.db`. It is separate from the data of stock-ai.
- `docker compose` takes the project name from the folder. `docker compose ps` in each folder therefore lists only the containers of that folder.

## Notes

- When ESPN logs you out, the background program will send one "cookie expired" alert (SPEC 6.3, not written yet).
  Copy a fresh `espn_s2` and `SWID` into `.env`. Then run `docker compose up -d`.
  Do not use `restart`, because `restart` does not read `.env` again.
- A later option (not built): run `ffai serve` on the VM and bind it to `127.0.0.1`.
  Reach it from the laptop over an SSH tunnel, as with the dashboard of stock-ai (`-L 8765:localhost:8765`).
  The extension then does not need a local Python process.
