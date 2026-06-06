# Google Calendar (optional)

NV-Disruptron can read calendar context for commute-aware alerts. OAuth tokens are shared via `platform/shared/google_calendar_client.py`.

## Setup

1. Create a Google Cloud OAuth client (Desktop app).
2. Export credentials:

```bash
export GOOGLE_CALENDAR_CLIENT_ID="..."
export GOOGLE_CALENDAR_CLIENT_SECRET="..."
```

3. Run auth (when calendar CLI is wired):

```bash
./scripts/disruptron configure
# follow printed calendar-auth instructions
```

4. Validate:

```bash
./scripts/disruptron validate
# prints calendar connected: true/false
```

Tokens are stored outside the repo. Never commit credentials or token files.
