# Gmail connector

OAuth via shared [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md).

**Callback:** `{API_PUBLIC_URL}/api/connectors/oauth/gmail/callback`

**Scope:** `https://www.googleapis.com/auth/gmail.modify`

## Agent tools

| Action | Description |
|--------|-------------|
| `gmail.messages.list` | List messages (`max_results`, optional `q`) |
| `gmail.messages.get` | Get message (`message_id`) |
| `gmail.messages.send` | Send email (`to`, `subject`, `body`) |

## Code

- `backend/app/connectors/gmail.py`
- `backend/app/connectors/google_vendor_oauth.py`
