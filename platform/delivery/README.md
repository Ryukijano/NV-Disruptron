# delivery

Push notifications and channel integrations.

| Component | Path | Role |
|-----------|------|------|
| **outputs-api** | `outputs-api/` | One-way push API → Telegram (`:8010`) |
| **telegram** | `telegram/` | Shared Telegram helpers |

## Configure channels

```bash
./scripts/disruptron configure --channels
```

## outputs-api

```bash
cd outputs-api && uv sync && ./start.sh
curl -s localhost:8010/health
```

Symlink: `outputs-api` → `platform/delivery/outputs-api`

## Docs

- [docs/GOOGLE_CALENDAR.md](docs/GOOGLE_CALENDAR.md)
- [../../features/agent/docs/CHANNELS.md](../../features/agent/docs/CHANNELS.md)
