# Browser extension v2 — expanded surfaces + usage signals

Date: 2026-08-03  
Baseline: v1 closed on tip `92fe0dde`

## New hosts (explicit allowlist — no silent expansion)

| Surface | Hosts | Injection |
|---------|-------|-----------|
| Salesforce | `*.lightning.force.com`, `*.salesforce.com`, `*.force.com` | content script |
| Slack | `app.slack.com` | content script |
| Careers/about | any (path markers) | `activeTab` inject (`company.js`) |

## Catalog (non-duplication)

| Intent | Catalog action | Not used |
|--------|----------------|----------|
| SF lead search/create | `salesforce.leads.search` / `salesforce.leads.create` | Lightning DOM |
| Slack identity | `slack.users.info` + Apollo/HubSpot reads | message scraping/send |
| Careers firmographics | `apollo.organizations.search` + HubSpot writes | job-board crawl |

## Usage signals

`POST /api/extension/usage-signal` → `audit_events.action = extension.usage_signal`  
Records allowlisted and non-allowlisted hosts the user tries to enrich.

## Live proof — PASS

Script: `scripts/live-extension-v2-smoke.py`

- Surface: `careers_about` (`https://www.acme-example.com/careers`)
- Usage signal outside allowlist: `host_allowlisted=false`
- Write: `hubspot.lists.create` via durable confirmationToken
- run_id `4ec4829a-25f7-4f99-ab86-197b468a9cc8`
- `execution_outcome_finalized` … `source=browser_extension` … `notification_emitted=True`
- notification `df7edb69-f9b4-4b5a-a9ea-bb0635ec93f9`
- Outcomes: https://gravitre.app/outcomes/4ec4829a-25f7-4f99-ab86-197b468a9cc8
