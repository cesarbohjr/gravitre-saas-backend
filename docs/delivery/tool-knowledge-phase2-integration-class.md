# Tool Knowledge — Phase 2 integration_class taxonomy (2026-08-11)

**Field:** `integrationClass` on each catalog vendor `to_dict()` row (`backend/app/connectors/action_catalog/integration_taxonomy.py`).  
**Does not replace** ActionSpec `kind` / `destructive` / `requires_approval`.

## Classes

| Class | Meaning |
| -- | -- |
| `OPEN_API` | Public developer API; no Gravitre-side vendor app approval for core REST surface |
| `OPEN_API_CUSTOMER_ENTITLEMENT` | API open, usable surface depends on customer SaaS plan / property entitlements |
| `DEVELOPER_APPROVAL` | Gravitre needs vendor app/token approval (e.g. Meta Marketing when connector exists) |
| `MCP_AVAILABLE` | Official vendor MCP exists; **prefer native ActionSpec** when already shipped |
| `LICENSED_PARTNER_ONLY` | Separate business/content agreement required (none in Wave 1 catalog set) |

## Catalog vendors (covered)

| Vendor | Class | MCP preference |
| -- | -- | -- |
| hubspot, salesforce, slack, github, jira, confluence, airtable, stripe, mailchimp, sendgrid, zendesk, intercom | OPEN_API | n/a |
| google_analytics, google_search_console, gmail, google_drive (+ Workspace family), microsoft365 (+ Teams/Outlook), quickbooks, xero, aws_s3 | OPEN_API_CUSTOMER_ENTITLEMENT | n/a |
| notion, asana, clickup, monday | MCP_AVAILABLE | **native_actionspec** (do not duplicate) |

## Missing Wave 1 vendors (planning only — no tool knowledge yet)

| Vendor | Class |
| -- | -- |
| gitlab, trello, linear, woocommerce, wordpress, brevo, cloudflare | OPEN_API |
| paypal, shopify, azure, google_cloud | OPEN_API_CUSTOMER_ENTITLEMENT |
| meta_marketing | DEVELOPER_APPROVAL |

## MCP decision (Notion / Asana / ClickUp / monday)

Official MCP is known; native connectors already live in the 696-action catalog. Recommendation matches prior MCP portability audit: keep native ActionSpec + optional org MCP overlay via `mcp_catalog_sync` — **no redundant second connector path**.
