# Production Deployment

Step-by-step record of how LinkDooni was deployed to a Hetzner CPX22 VPS, with the reasoning behind each choice. This is the runbook for redeploys and a teaching artifact.

Stack: Ubuntu 24.04 + Docker Compose + PostgreSQL + the bot, all on a single VPS. Telegram long polling (no inbound HTTP needed).

---

## 1. Provision the VPS (Hetzner Cloud)

1. Sign up at https://www.hetzner.com/cloud, verify identity, add a payment method.
2. Create a Project (e.g. `LinkDooni`).
3. **Add Server**:
   - Location: **Nuremberg** or **Helsinki** (low latency to Telegram + global)
   - Image: **Ubuntu 24.04**
   - Type: **Regular Performance → x86 (AMD) → CPX22** (2 vCPU, 4 GB RAM, 80 GB SSD, ~€9.99/mo). Cheaper Cost-Optimized tiers (CX/CAX) are equally fine; pick whatever has stock.
   - **SSH keys**: paste your public key (`cat ~/.ssh/id_ed25519.pub`) so login is key-based, not password-based.
   - Volumes / Placement groups / Labels / Cloud config: skip for a single-server setup.

**Why a Cloud Firewall before the server starts:** Hetzner's network-edge firewall rejects unwanted traffic before it hits your VM. It's free and additive to `ufw` on the box (defense in depth).

4. **Firewall** rules:
   - Inbound: `TCP 22` (SSH) from anywhere; `ICMP` from anywhere (for ping).
   - Outbound: leave default (allow all). Long-polling bots need outbound to `api.telegram.org` and to fetch URL metadata.

Click **Create & Buy now**. The server boots in ~20 seconds; note its public IP.

```bash
# From your laptop:
ping <server-ip>
ssh root@<server-ip>
```

---

## 2. Harden the server

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg git ufw fail2ban
```

**Why each:**
- `ufw` — host-level firewall, second layer behind Hetzner Cloud Firewall.
- `fail2ban` — bans IPs after repeated failed SSH attempts. Cheap protection against brute-force.
- `git` — to pull the project.
- `ca-certificates`, `curl`, `gnupg` — required to add the Docker apt repo securely.

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

systemctl enable --now fail2ban
```

The server now refuses every inbound connection except SSH.

---

## 3. Install Docker (official repo, not Ubuntu's older one)

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
```

**Why upstream Docker, not `apt install docker.io`:** Ubuntu's repo lags. Upstream gives you the current Docker Engine and the modern `docker compose` plugin (one binary, not the legacy `docker-compose` Python script).

Verify:

```bash
docker --version
docker compose version
```

---

## 4. Clone the repo

```bash
mkdir -p /srv && cd /srv
git clone https://github.com/erfan-kanani/LinkDooni.git linkdooni
cd linkdooni
```

`/srv` is the conventional Linux location for service data. Each service gets its own directory there.

---

## 5. Create `.env` with secrets

```bash
cat > /srv/linkdooni/.env <<'EOF'
TELEGRAM_BOT_TOKEN=replace-me
LOG_LEVEL=INFO
CONFIG_DIR=app/config
EOF
chmod 600 .env
```

Then `nano .env` and paste the real bot token from @BotFather.

**What's intentionally NOT in this `.env`:**
- `DATABASE_URL` — overridden by docker-compose to point at the `db` service inside the container network (`postgresql+asyncpg://linkdooni:linkdooni@db:5432/linkdooni`). Inside a container `localhost` means the container itself, not the database, so the override is mandatory.
- `LINKDOONI_AUTO_CREATE_DB` — overridden to `false`. In production we want Alembic to own the schema, not the bot at startup. Auto-create races with migrations.

`chmod 600` ensures only root can read the file. Don't ever commit `.env` to git (the repo's `.gitignore` already blocks it).

---

## 6. Start the stack

```bash
docker compose up -d --build
```

This builds the bot image from the [Dockerfile](Dockerfile) (`python:3.12-slim` + `uv sync`) and starts two containers:
- `linkdooni-postgres` — Postgres 16, with port 5432 bound only to `127.0.0.1` so it's not reachable from the internet.
- `linkdooni-bot` — the bot, depending on the db's healthcheck.

Both have `restart: unless-stopped` so they survive reboots and crashes.

---

## 7. Run migrations

The first start crashes with `relation "users" does not exist` because the schema is empty and we disabled auto-create. Apply migrations:

```bash
docker compose run --rm bot uv run alembic upgrade head
```

`docker compose run --rm` spins up a one-shot container, runs the command, and removes itself. It uses the same image and env as the long-running bot service.

Then restart the bot to clear its connection pool:

```bash
docker compose restart bot
docker compose logs bot --tail=20
```

You should see `bot_starting` and `Run polling for bot @link_dooni_bot`. Send `/start` to the bot in Telegram to confirm.

---

## Daily operations

```bash
cd /srv/linkdooni

# Live tail
docker compose logs bot -f

# Status
docker compose ps

# Restart only the bot
docker compose restart bot

# Hard restart everything
docker compose down && docker compose up -d

# Deploy new code
git pull
docker compose up -d --build
# If migrations changed:
docker compose run --rm bot uv run alembic upgrade head
docker compose restart bot
```

---

## Architecture summary

```
Internet
   │
   ▼
Hetzner Cloud Firewall  ──  drops everything except :22 and ICMP
   │
   ▼
Ubuntu VM (CPX22)
   │   ufw  ──  same rules, host-level
   │   fail2ban  ──  bans repeated SSH failures
   │
   └── Docker Engine
        ├── linkdooni-postgres  (127.0.0.1:5432, internal net "linkdooni_default")
        └── linkdooni-bot       (no ports exposed; outbound long-polling to api.telegram.org)
```

The bot makes only outbound connections; nothing on the server listens on a public port besides SSH.

---

## Things deferred (do later)

1. **Regenerate the bot token** if it was ever pasted into chat or logs.
2. **Postgres backups.** Daily `pg_dump` → Hetzner Storage Box (€1.20/mo for 100 GB) or Backblaze B2. Without this, a disk failure is total data loss.
3. **Non-root SSH user.** Create a normal user, give it `sudo`, add your SSH key, then `PermitRootLogin no` in `/etc/ssh/sshd_config`. Smaller blast radius if your key ever leaks.
4. **Restrict SSH source IP** in the Hetzner Cloud Firewall to your home/office IP. Removes 99% of brute-force noise.
5. **Reverse proxy (Caddy or Traefik)** — only when you start hosting HTTP services on this box. Not needed for a polling-only bot.
6. **Monitoring.** A free UptimeRobot check that pings the bot's `/getMe` endpoint, or a 5-line cron that emails you when `docker compose ps` shows the bot is down.

---

## Cost

- VPS: €9.99/mo
- Backups (when added): ~€1.20/mo
- **Total: ~€11/mo** for a production-grade single-tenant Telegram bot.
