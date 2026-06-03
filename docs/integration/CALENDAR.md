# Google Calendar (STA-23 stretch)

## Connector setup

1. Create connector `type=google_calendar`.
2. Store secret `access_token` — OAuth access token with Calendar API scope (`https://www.googleapis.com/auth/calendar`).
3. Use Google Cloud OAuth consent + token exchange; full OAuth UI can follow STA-13 pattern in a later pass.

## Tool actions

| Action | Description |
|--------|-------------|
| `calendar.freebusy` | Query free/busy (`calendar_id`, optional `time_min`/`time_max`) |
| `calendar.events.create` | Create event (`summary`, `start`, `end`, optional `attendees`) |

Scopes: `calendar:read`, `calendar:write`, or `calendar:*`.
