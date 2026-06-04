# Jira Cloud OAuth (STA-36)

## Platform setup (operator)

1. Create an OAuth 2.0 (3LO) app in the [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/).
2. **Callback URL:**

```text
{API_PUBLIC_URL}/api/connectors/oauth/jira/callback
```

3. **Scopes:** `read:jira-work`, `write:jira-work`, `offline_access`
4. Set on API host:

```env
JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=your_64_character_hex_key_here
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

## Customer flow

**Connectors → Connect Jira** (OAuth). The first accessible Jira Cloud site is stored as `connectors.config.cloud_id`.

## Readiness check

```powershell
npm run jira:check
```

## Tool actions

See [JIRA_ACTIONS.md](./JIRA_ACTIONS.md).

## Code

- `backend/app/connectors/jira_oauth.py`
- `backend/app/connectors/jira.py`
- `backend/app/routers/connector_oauth.py`
