# PagerDuty OAuth (STA-37)

## Platform setup (operator)

1. Register an OAuth app in [PagerDuty Developer](https://developer.pagerduty.com/).
2. **Redirect URL:**

```text
{API_PUBLIC_URL}/api/connectors/oauth/pagerduty/callback
```

3. Set on API host:

```env
PAGERDUTY_CLIENT_ID=
PAGERDUTY_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=your_64_character_hex_key_here
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

## Customer flow

**Connectors → Connect PagerDuty** (OAuth). On connect, the API stores a webhook signing secret and attempts to register a PagerDuty webhook subscription for `incident.triggered` and `incident.acknowledged`.

## Triggers

See [PAGERDUTY_TRIGGERS.md](./PAGERDUTY_TRIGGERS.md).

## Readiness

```powershell
Invoke-RestMethod "https://<api-host>/api/connectors/oauth/pagerduty/status"
```

## Code

- `backend/app/connectors/pagerduty_oauth.py`
- `backend/app/services/pagerduty_trigger_service.py`
