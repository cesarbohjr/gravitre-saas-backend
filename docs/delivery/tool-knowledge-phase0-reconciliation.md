# Tool Knowledge — Phase 0 catalog reconciliation (2026-08-11)

**Live catalog:** 78 vendors · **696** ActionSpecs (`app.connectors.action_catalog.registry`).  
**SoT:** `backend/app/connectors/action_catalog/vendor_definitions.py`  
**Do not build** Observation / Action / Governance layers — they already exist (`catalog_write_authority`, `kind`/`destructive`/`requires_approval`).

## Naming aliases

| Proposal name | Catalog id(s) |
| -- | -- |
| GA4 | `google_analytics` |
| Google Search Console | `google_search_console` |
| Google Workspace | family: `gmail`, `google_drive`, `google_docs`, `google_sheets`, `google_calendar` (46 actions) |
| Microsoft Graph | `microsoft365` (+ `microsoft_teams`, `outlook`) |
| monday.com | `monday` |
| QuickBooks Online | `quickbooks` |
| AWS | `aws_s3` only (not umbrella `aws`) |

## Fully covered (connector + live ActionSpecs)

| Vendor | vendor_id | Actions |
| -- | -- | -- |
| HubSpot | hubspot | 28 |
| Salesforce | salesforce | 14 |
| Slack | slack | 14 |
| GitHub | github | 15 |
| Asana | asana | 12 |
| ClickUp | clickup | 13 |
| monday.com | monday | 11 |
| Notion | notion | 12 |
| Jira | jira | 10 |
| Confluence | confluence | 12 |
| Airtable | airtable | 8 |
| Stripe | stripe | 9 |
| QuickBooks Online | quickbooks | 16 |
| Xero | xero | 9 |
| Mailchimp | mailchimp | 9 |
| SendGrid | sendgrid | 8 |
| Zendesk | zendesk | 10 |
| Intercom | intercom | 12 |
| GA4 | google_analytics | 7 |
| Google Search Console | google_search_console | 4 |

## Partial / family coverage

| Vendor | Status |
| -- | -- |
| Google Workspace | Covered as **5** vendors (46 actions), not one id |
| Microsoft Graph | Covered primarily as `microsoft365` (25) + Teams/Outlook |
| AWS | Only `aws_s3` (8) — not full AWS cloud surface |

## Genuinely missing (no ActionSpecs)

GitLab · Trello · Linear · PayPal · Shopify · WooCommerce · WordPress · Brevo · Meta Marketing · Cloudflare · Azure · Google Cloud

Notes: Shopify has an HTTP profile stub without ActionSpecs; Linear appears in data-source/enrichment orphans only — **not** catalog-present.

## MCP (Notion / Asana / ClickUp / monday)

All four already have **native** ActionSpec + API connectors. Generic MCP sync (`mcp_catalog_sync`) can add `mcp_*` vendors, but **prefer existing native connectors** — do not duplicate with a redundant MCP path.

## Scope for Tool Knowledge (Phases 1–4)

1. Attach `tool_expertise` knowledge packs to **existing** catalog vendors only.  
2. Missing Wave 1 vendors → connector ActionSpec initiative later; **no** tool-knowledge ingest without a connector to attach to.  
3. Priority Wave 1 knowledge ingest: HubSpot, Salesforce, Slack, Stripe, Notion, GitHub, Jira, SendGrid, Zendesk, GA4 (+ Workspace/M365 family stubs as needed).
