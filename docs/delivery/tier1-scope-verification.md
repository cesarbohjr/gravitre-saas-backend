# Tier 1 OAuth scope verification (STA-276)

Verified **2026-06-24** against live HubSpot/Salesforce OAuth config in repo and operator docs.

## HubSpot

**OAuth authorize scopes** (`backend/app/connectors/hubspot_oauth.py` → `HUBSPOT_REQUIRED_SCOPES` + optional `automation`):

| HubSpot OAuth scope | Catalog / tool coverage | Verified |
|---------------------|-------------------------|----------|
| `crm.objects.contacts.read` | v1 `contacts.get`, `contacts.search`; v4 `companies.search` (read path) | ✅ |
| `crm.objects.contacts.write` | v2 `contacts.create`, `contacts.update` | ✅ |
| `crm.objects.deals.read` | v1 `deals.get`; v4 `pipelines.list` | ✅ |
| `crm.objects.deals.write` | v2 `deals.create`; v3 `deals.update_stage` | ✅ |
| `crm.objects.companies.read` | v4 `companies.search` | ✅ (added 2026-06-24) |
| `crm.objects.tickets.write` | v4 `tickets.create` | ✅ (added 2026-06-24) |
| `crm.objects.notes.write` | v2 `notes.create` | ✅ (aligned with `HUBSPOT_PLATFORM_SETUP.md`) |
| `crm.lists.read` / `crm.lists.write` | v3 `lists.add_contact` | ✅ |
| `oauth` | Token introspection / refresh | ✅ |
| `automation` (optional) | v3 `sequences.enroll` | ✅ |

**Catalog scope suffixes** (`hubspot:contacts:read`, etc.) are **Gravitre RBAC labels**, not HubSpot OAuth scope strings. They map to the OAuth scopes above via tool permissions — no rename needed.

**Operator action:** Ensure the HubSpot developer app Auth tab includes all scopes listed in `HUBSPOT_PLATFORM_SETUP.md` (updated to match code). Re-connect existing org connectors after adding new scopes.

## Salesforce

**OAuth authorize scopes** (`backend/app/connectors/salesforce_oauth.py`):

| Salesforce OAuth scope | Meaning | Verified |
|------------------------|---------|----------|
| `api` | Full REST API access for connected user | ✅ Covers all v1–v3 catalog tools |
| `refresh_token` | Offline refresh | ✅ |

**Catalog scope suffixes** (`salesforce:leads:read`, `salesforce:opportunities:write`, etc.) are **Gravitre RBAC labels**. Salesforce uses the broad `api` scope; object-level suffixes do not map 1:1 to Salesforce OAuth scope names (Salesforce uses permission sets/profiles server-side).

## Supabase (out of Tier 1 OAuth scope)

Supabase is **not** a customer OAuth connector in the Tier 1 audit:

| Surface | Role |
|---------|------|
| **Supabase Auth** | Platform login (`*.supabase.co/auth/v1/callback`) |
| **PostgreSQL source connector** | Org SQL + RAG knowledge sync |
| **Supabase storage** | Platform backend (service role) |

See `docs/delivery/tier1-connector-audit-latest.json` → `supabase` block.

## References

- `backend/app/connectors/hubspot_oauth.py`
- `backend/app/connectors/salesforce_oauth.py`
- `docs/integration/HUBSPOT_PLATFORM_SETUP.md`
- `npm run tier1:audit` / `npm run tier1:smoke`
