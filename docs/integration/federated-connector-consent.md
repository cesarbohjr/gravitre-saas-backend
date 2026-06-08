# Federated connector consent (STA-117)

Partner orgs with an **active B2B partnership** (STA-116) can share **read-only** connector tool access via time-boxed grants.

## Flow

1. **Grantor org** (connector owner) proposes grant with allowed read actions + expiry
2. **Grantee org** admin accepts → receives one-time `accessToken`
3. Grantee agents invoke tools with `federationToken` (or `federationGrantId` for org-scoped resolution)
4. Tool runs against grantor connector credentials; audit logs `federation.tool.invoke`

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/federation/connector-grants` | List grants for current org |
| GET | `/api/federation/connector-grants/{id}` | Grant detail |
| POST | `/api/federation/connector-grants` | Propose grant (grantor admin) |
| POST | `/api/federation/connector-grants/{id}/accept` | Grantee accepts; returns token |
| POST | `/api/federation/connector-grants/{id}/reject` | Grantee rejects |
| POST | `/api/federation/connector-grants/{id}/revoke` | Either party revokes |

### Propose body

```json
{
  "granteeOrgId": "00000000-0000-0000-0000-000000000002",
  "connectorId": "hubspot-connector-uuid",
  "allowedActions": ["hubspot.contacts.search", "hubspot.contacts.get"],
  "label": "Partner CRM read slice",
  "expiresInHours": 24
}
```

## Tool invoke

Pass token on workflow/agent tool parameters:

```json
{
  "federationToken": "<accessToken from accept>",
  "query": "acme@example.com"
}
```

Only actions listed in `allowedActions` are permitted. Write/create/update tools are rejected at grant creation.

## Audit

- `federation.grant.proposed` / `.accepted` / `.rejected` / `.revoked` / `.expired`
- `federation.tool.invoke`

## Related

- [B2B handoff protocol](./b2b-handoff-protocol.md) — partnership prerequisite
- STA-118 delegate task to external org — `docs/integration/delegated-external-tasks.md`

## Key files

- `supabase/migrations/20260608190000_federated_connector_grants.sql`
- `backend/app/services/federated_connector_service.py`
- `backend/app/routers/federation.py` (connector-grants routes)
- `backend/app/services/tool_service.py` (`federationToken` handling)
