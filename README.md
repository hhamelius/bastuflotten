# Bastuflotten 🛁

Slack booking bot for Bastuflotten — the shared sauna float on the lake.

## Slash commands

| Command | Alias | Description |
|---|---|---|
| `/boka` | `/book` | Open booking form (modal) |
| `/avboka <id>` | `/cancel <id>` | Cancel a booking by ID |
| `/lista [offset]` | `/list [offset]` | List upcoming bookings (4 at a time) |
| `/lista-avbokade` | `/cancelled` | List cancelled bookings |

## Local development

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Slack app (see below)
- [ngrok](https://ngrok.com/) for local webhook testing

### Setup

```bash
cd ~/projects/bastuflotten
uv venv && uv pip install -e .
cp .env.example .env
# Edit .env with your SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET
mkdir -p /tmp/bastuflotten-data
uv run uvicorn bastuflotten.app:app --reload --port 8000
```

### ngrok (local testing)

```bash
ngrok http 8000
```

Use the ngrok HTTPS URL as your Slack request URL:
`https://<ngrok-id>.ngrok.io/slack/events`

## Slack app setup

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Name: Bastuflotten, pick your workspace
3. OAuth & Permissions → Bot Token Scopes: `commands`, `chat:write`, `chat:write.public`
4. Interactivity & Shortcuts → On → Request URL: `https://bastuflotten.hahamelius.se/slack/events`
5. Slash Commands → create all 8 (see README body), same Request URL
6. Install to workspace → copy Bot User OAuth Token → SLACK_BOT_TOKEN
7. Basic Information → Signing Secret → SLACK_SIGNING_SECRET
8. In Slack: `/invite @Bastuflotten` in #bastuflotten

## Slash commands to register

All pointing to `https://bastuflotten.hahamelius.se/slack/events`:

| Command | Hint |
|---|---|
| `/boka` | |
| `/book` | |
| `/avboka` | `<boknings-id>` |
| `/cancel` | `<booking-id>` |
| `/lista` | `[offset]` |
| `/list` | `[offset]` |
| `/lista-avbokade` | |
| `/cancelled` | |

## Deploy to Hetzner (49.12.47.37)

```bash
ssh root@49.12.47.37
curl -fsSL https://get.docker.com | sh
git clone <your-repo-url> /opt/bastuflotten
cd /opt/bastuflotten
cp .env.example .env && nano .env
docker compose up -d
```

### DNS records (Hetzner DNS console)

| Type | Name | Value |
|---|---|---|
| A | `@` | `49.12.47.37` |
| A | `bastuflotten` | `49.12.47.37` |

### Update

```bash
ssh root@49.12.47.37
cd /opt/bastuflotten && git pull
docker compose up -d --build
```

### Useful commands

```bash
docker compose logs -f bot
curl https://bastuflotten.hahamelius.se/health
docker compose cp bot:/data/bookings.db ./bookings-backup.db
```
