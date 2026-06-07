# Telegram bot architecture

NV-Disruptron has **three** Telegram integration paths. Only **one** should long-poll `getUpdates` on a given bot token.

## Recommended (hackathon / Spark)

| Role | Component | Command |
|------|-----------|---------|
| **Interactive chat** | OpenClaw gateway | `openclaw gateway start` + `./scripts/disruptron configure --channels` |
| **Web chat** | disruptron-api + React | `features/delivery/disruptron-api/start.sh` |
| **Push alerts & morning digest** | disruptron-api `sendMessage` | Same API — no extra polling |

Set in `.env`:

```bash
DISRUPTRON_TELEGRAM_MODE=openclaw
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_ALLOW_FROM=<your numeric user id>
```

Then:

```bash
./scripts/disruptron configure --channels
openclaw gateway restart
openclaw pairing approve telegram <CODE>   # if using pairing
```

**Do not** run `features/delivery/telegram-bot/start.sh` while OpenClaw owns the token.

### Why OpenClaw?

- Native **partial streaming** to Telegram
- **Heartbeat** every 10m with `target: last` (proactive disruption alerts)
- Full **MCP tool** surface (TfL, EV, wards, calendar)
- Same agent id (`disruptron`) as web chat

### What disruptron-api adds

- `POST /v1/push/alert` — fan-out to `/subscribe_alerts` Telegram users
- `POST /v1/push/daily` — morning digest to `/subscribe_daily` users
- **Scheduler** — auto morning digest at `DISRUPTRON_DAILY_DIGEST_HOUR` (default 08:00 London)
- **Web SSE** — same pushes appear in the Notifications tab for web subscribers

---

## Alternative: standalone telegram-bot

Use when **OpenClaw gateway is not running Telegram**.

```bash
DISRUPTRON_TELEGRAM_MODE=telegram-bot
DISRUPTRON_CHAT_MODE=agent          # on disruptron-api
features/delivery/disruptron-api/start.sh
features/delivery/telegram-bot/start.sh
```

`telegram-bot` polls Telegram and forwards messages to `disruptron-api` `/v1/chat`.

---

## Push-only (no interactive bot)

```bash
DISRUPTRON_TELEGRAM_MODE=push-only
```

Use disruptron-api push endpoints from cron/CI. Users subscribe via another channel or manual chat_id list.

---

## Legacy: platform/delivery/outputs-api

Older combined layout (bot + push + OpenClaw fallback). Prefer **features/delivery/disruptron-api** for new work.

---

## Env reference

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | BotFather token (all paths) |
| `TELEGRAM_ALLOW_FROM` | OpenClaw allowlist (numeric user id) |
| `DISRUPTRON_TELEGRAM_MODE` | `openclaw` \| `telegram-bot` \| `push-only` |
| `DISRUPTRON_PUSH_SECRET` | Protect `/v1/push/*` and `/v1/digest/run` |
| `DISRUPTRON_DAILY_DIGEST_HOUR` | London time (default `8`) |
| `DISRUPTRON_SCHEDULER_ENABLED` | `1` to run morning digest scheduler |

See also [features/agent/docs/CHANNELS.md](../features/agent/docs/CHANNELS.md).
