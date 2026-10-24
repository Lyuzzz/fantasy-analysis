# Deploy (background phase, same VM as stock-ai)

> **Not ready, do not deploy yet.** The background part is paused (SPEC section 0). `python -m ffai run`, the container command, exits at once because `check` is not written yet. With `restart: unless-stopped` that would restart in a loop. This file and `docker-compose.yml` are prepared so the deploy is quick later.

ffai goes on the **same GCP VM as stock-ai**, as its own repo and its own Docker Compose project. It is not part of stock-ai's compose file or process, so a crash or out-of-memory in one cannot take down the other. Nothing in stock-ai's repo is touched.

## What is already on the VM (from stock-ai's DEPLOY.md)

| Item | Value |
|---|---|
| VM name | `stock-ai` |
| Zone | `us-west1-a` |
| Size | e2-micro, 1 GB RAM plus 1 GB swap |
| Access | `vmssh` alias = `gcloud compute ssh stock-ai --tunnel-through-iap --zone=us-west1-a` |
| Docker + Compose, git | installed |
| stock-ai | `~/stock-ai-`, containers `stock-ai-monitor` and `stock-ai-api` (port `127.0.0.1:8000`) |

So there is **no new VM and nothing to install**. The container is `ffai-monitor`, limited to 256 MB, with no published ports.

## First deploy

1. **Deploy key.** On the VM, make a second read-only key for this repo (GitHub allows a deploy key on one repo only):
   ```bash
   vmssh
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519_ffai
   cat ~/.ssh/id_ed25519_ffai.pub
   ```
   Add it in GitHub: repo **Settings -> Deploy keys**, leave "Allow write access" unchecked. Then tell git to use it for this repo:
   ```bash
   git clone -c core.sshCommand="ssh -i ~/.ssh/id_ed25519_ffai" git@github.com:Lyuzzz/fantasy-analysis.git
   cd fantasy-analysis
   git config core.sshCommand "ssh -i ~/.ssh/id_ed25519_ffai"
   ```
2. **Ship `.env`** from your laptop. It is gitignored, so it does not come with `git pull`:
   ```bash
   gcloud compute scp .env stock-ai:~/fantasy-analysis/ --tunnel-through-iap --zone=us-west1-a
   ```
   On the VM: `chmod 600 ~/fantasy-analysis/.env`.
3. **Start:** `cd ~/fantasy-analysis && docker compose up -d --build`.
4. **Check the memory.** The VM is small, so look right after the first start:
   ```bash
   docker stats --no-stream      # ffai-monitor should stay far below 256 MB
   free -m                       # stock-ai must still have room
   ```

## Update

Add an alias next to `vmdeploy` in `~/.zshrc`:

```bash
alias ffdeploy='vmssh --command="cd fantasy-analysis && git pull && docker compose up -d --build"'
```

## Look at it

- Logs: `docker compose logs -f ffai` (in `~/fantasy-analysis`)
- State: SQLite file `./data/ffai.db`, separate from stock-ai's.
- `docker compose` takes the project name from the folder, so `docker compose ps` in each folder lists only its own containers.

## Notes

- If ESPN logs you out, the background part will send one "cookie expired" alert (SPEC 6.3, not written yet). Copy a fresh `espn_s2` and `SWID` into `.env`, then run `docker compose up -d` (not `restart`, which does not re-read `.env`).
- Later option, not built: run `ffai serve` on the VM bound to `127.0.0.1` and reach it from the laptop through an SSH tunnel, like stock-ai's dashboard (`-L 8765:localhost:8765`). Then the extension would not need a local Python process.
