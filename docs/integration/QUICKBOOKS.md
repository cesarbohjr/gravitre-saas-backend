# QuickBooks Online OAuth (STA-33)

## Platform setup (operator)

1. Create an app in the [Intuit Developer Portal](https://developer.intuit.com/) with **QuickBooks Online Accounting** scope.
2. **Redirect URI:**

```text
{API_PUBLIC_URL}/api/connectors/oauth/quickbooks/callback
```

3. Set on API host:

```env
QUICKBOOKS_CLIENT_ID=
QUICKBOOKS_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=your_64_character_hex_key_here
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

Optional sandbox app (used for org connectors in `staging` / `sandbox` environment):

```env
QUICKBOOKS_SANDBOX_CLIENT_ID=
QUICKBOOKS_SANDBOX_CLIENT_SECRET=
```

## Customer flow

**Connectors → Connect QuickBooks** (OAuth). Intuit returns `realmId` (company id) on callback; stored in `connectors.config.realm_id` with encrypted tokens.

## Readiness check

```powershell
npm run quickbooks:check
# or
Invoke-RestMethod "https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/quickbooks/status"
```

Push operator secrets to Railway (from `backend/.env.operator.local`):

```powershell
npm run quickbooks:railway
```

**Intuit Developer Portal → Keys & OAuth → Redirect URIs** must include exactly:

```text
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/quickbooks/callback
```

For local backend testing, also add:

```text
http://localhost:8000/api/connectors/oauth/quickbooks/callback
```

## Tool actions (STA-34)

See [QUICKBOOKS_ACTIONS.md](./QUICKBOOKS_ACTIONS.md).

## Code

- `backend/app/connectors/quickbooks_oauth.py`
- `backend/app/connectors/quickbooks.py`
- `backend/app/routers/connector_oauth.py`
