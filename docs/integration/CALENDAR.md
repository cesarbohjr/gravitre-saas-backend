# Google Calendar (STA-23)

## Connector setup

1. Ensure **Gravitre OAuth** is configured on Railway (`npm run google:fill-env` → `npm run google:railway`). See [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md).
2. Connectors → **Google Calendar** → **Connect with Google** (OAuth; Calendar API scope).
3. (Optional legacy) Manual `access_token` secret on a `google_calendar` connector still works if OAuth is unavailable.

## Tool actions

| Action | Description |
|--------|-------------|
| `calendar.freebusy` | Query free/busy (`calendar_id`, optional `time_min`/`time_max`) |
| `calendar.events.create` | Create event (`summary`, `start`, `end`, optional `attendees`) |

Scopes: `calendar:read`, `calendar:write`, or `calendar:*`.

## OAuth callback

`{API_PUBLIC_URL}/api/connectors/oauth/google_calendar/callback`
