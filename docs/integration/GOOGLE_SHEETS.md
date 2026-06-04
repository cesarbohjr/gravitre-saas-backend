# Google Sheets connector

OAuth via shared [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md).

**Callback:** `{API_PUBLIC_URL}/api/connectors/oauth/google_sheets/callback`

**Scope:** `https://www.googleapis.com/auth/spreadsheets.readonly`

## Agent tools

| Action | Description |
|--------|-------------|
| `sheets.spreadsheets.get` | Get spreadsheet metadata (`spreadsheet_id`) |
| `sheets.values.get` | Read range (`spreadsheet_id`, `range`) |

## Code

- `backend/app/connectors/google_sheets.py`
- `backend/app/connectors/google_vendor_oauth.py`
