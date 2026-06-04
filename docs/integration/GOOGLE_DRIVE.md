# Google Drive connector

OAuth via shared [GOOGLE_OAUTH.md](./GOOGLE_OAUTH.md).

**Callback:** `{API_PUBLIC_URL}/api/connectors/oauth/google_drive/callback`

**Scope:** `https://www.googleapis.com/auth/drive.readonly`

## Agent tools

| Action | Description |
|--------|-------------|
| `drive.files.list` | List files (`page_size`, optional `q`) |
| `drive.files.get` | Get file metadata (`file_id`) |

## Code

- `backend/app/connectors/google_drive.py`
- `backend/app/connectors/google_vendor_oauth.py`
