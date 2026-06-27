# Tier 2 OAuth scope verification (STA-277)

Verified **2026-06-24** for QuickBooks and NetSuite financial connectors.

## Pilot default (STA-277 / STA-285)

| Tier | Pilot behavior |
|------|----------------|
| **v1 read** | Live API calls when OAuth connected |
| **v2/v3 write** | Implemented executors; demos should use **simulation mode** or require approval until customer IT grants write scopes |

## QuickBooks

**OAuth scopes** (Intuit app settings — accounting scope bundle):

| Intuit scope | Catalog coverage |
|--------------|------------------|
| `com.intuit.quickbooks.accounting` | All v1–v3 catalog actions (reads + writes) |

**Redirect URI:** `https://gravitre.app/api/connectors/oauth/quickbooks/callback`

**Railway env:** `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET` (+ optional sandbox pair)

**Catalog scope suffixes** (`quickbooks:invoices:read`, etc.) are Gravitre RBAC labels, not Intuit OAuth scope strings.

## NetSuite

**OAuth scopes** (NetSuite integration record — REST Web Services):

| NetSuite permission | Catalog coverage |
|---------------------|------------------|
| REST Web Services | Record CRUD via REST API |
| Customer / Invoice / Sales Order / Item / Fulfillment records | v1–v3 catalog actions |

**Connect-time fields:** NetSuite **account ID** (and optional sandbox) stored on connector config.

**Redirect URI:** `https://gravitre.app/api/connectors/oauth/netsuite/callback`

**Railway env:** `NETSUITE_CLIENT_ID`, `NETSUITE_CLIENT_SECRET` (+ optional sandbox pair)

**Write safety:**

- `journalentries.create` posts with `draft: true` by default
- `customers.update` limited to billing-contact fields only
- `salesorders.create` / `fulfillment.create` require explicit payloads (approval-gated in catalog)

## References

- `backend/app/connectors/quickbooks_oauth.py`
- `backend/app/connectors/netsuite_oauth.py`
- `npm run tier2:audit` / `npm run tier2:smoke`
