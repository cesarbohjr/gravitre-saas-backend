# Google Analytics (GA4) — STA-40

OAuth connector for Marketing Agent GA4 read access (Data API groundwork).

**Platform setup:** use the shared [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md) guide (`npm run google:setup`, `google:fill-env`, `google:railway`, `google:check`).

Redirect URI: `{API_PUBLIC_URL}/api/connectors/oauth/google_analytics/callback`

Env (either naming works): `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` or `GOOGLE_ANALYTICS_CLIENT_ID` / `GOOGLE_ANALYTICS_CLIENT_SECRET`

OAuth scope: `https://www.googleapis.com/auth/analytics.readonly`

## Customer flow

1. Admin → **Connectors** → **Google Analytics** → Connect with Google.
2. If the account has one GA4 property, it is linked automatically.
3. If multiple properties exist, pick one in the **Link GA4 property** dialog.

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/connectors/oauth/google_analytics/start` | Start OAuth |
| GET | `/api/connectors/oauth/google_analytics/callback` | OAuth callback |
| GET | `/api/connectors/{id}/google-analytics/properties` | List linkable properties |
| PUT | `/api/connectors/{id}/google-analytics/property` | Link `propertyId` |

Connector `config` after link: `property_id`, `property_name`, `property_resource`.

## Agent tools

- `analytics.properties.list` — list GA4 properties (Admin API)
- `analytics.reports.run` — run a GA4 report (Data API; requires linked `property_id`)

## Linear

- [STA-40](https://linear.app/staqbot/issue/STA-40) — OAuth + property linking ✅
- [STA-41](https://linear.app/staqbot/issue/STA-41) — GA4 v1 read actions ✅
- [STA-42](https://linear.app/staqbot/issue/STA-42) — Marketing attribution workflow ✅ — see [MARKETING_ATTRIBUTION.md](./MARKETING_ATTRIBUTION.md)

## Code

- `backend/app/connectors/google_vendor_oauth.py`
- `backend/app/connectors/google_analytics.py`
- `backend/app/routers/google_analytics.py`
