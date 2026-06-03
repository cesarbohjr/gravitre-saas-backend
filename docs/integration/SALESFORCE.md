# Salesforce OAuth (STA-30)

## Platform setup (operator)

1. Create a **Connected App** in Salesforce Setup → App Manager.
2. Enable **OAuth** with callback URL:

```text
{API_PUBLIC_URL}/api/connectors/oauth/salesforce/callback
```

3. Scopes: `api`, `refresh_token` (offline access).
4. Set on API host:

```env
SALESFORCE_CLIENT_ID=
SALESFORCE_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=your_64_character_hex_key_here
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

Optional sandbox app:

```env
SALESFORCE_SANDBOX_CLIENT_ID=
SALESFORCE_SANDBOX_CLIENT_SECRET=
```

## Customer flow

**Connectors → Connect Salesforce** (OAuth). Tokens stored encrypted per org.

## Readiness check

```powershell
Invoke-RestMethod "https://<api-host>/api/connectors/oauth/salesforce/status"
```

## Code

- `backend/app/connectors/salesforce_oauth.py`
- `backend/app/routers/connector_oauth.py`
