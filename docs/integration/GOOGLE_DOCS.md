# Google Docs connector

OAuth via shared [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md).

**Callback:** `{API_PUBLIC_URL}/api/connectors/oauth/google_docs/callback`

**Scope:** `https://www.googleapis.com/auth/documents.readonly`

## Agent tools

| Action | Description |
|--------|-------------|
| `docs.documents.get` | Get document (`document_id`) |

## Code

- `backend/app/connectors/google_docs.py`
- `backend/app/connectors/google_vendor_oauth.py`
