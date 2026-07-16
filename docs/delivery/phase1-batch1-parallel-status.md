# Phase 1 Batch 1 — parallel tip status (2026-07-16)

| Vendor | Status | Evidence |
|--------|--------|----------|
| HubSpot Batch 1b `tickets.get` | **PASS** | `phase1-hubspot-batch1b-tickets-get-live.json` — ticket `203092799418` @ `2026-07-16T09:20:00Z` |
| GitHub | **BLOCKED_EXTERNAL** | prior tip; needs smoke-org connect |
| Salesforce `query` | **BLOCKED_EXTERNAL** | `phase1-salesforce-batch1-live.json` — no connector; action `salesforce.query` implemented in code |
| Asana | **BLOCKED_EXTERNAL** | `phase1-asana-batch1-live.json` — no connector |
| Pipedrive `pipelines.list` | **PASS** | `phase1-pipedrive-batch1-live.json` @ `2026-07-16T18:55:30Z` connector `e6aa92f6…` |
| EngageBay | held | needs Cesar connect (STA-302) |
| NVD + CISA KEV | **PASS** | `phase1-nvd-cisa-batch1-live.json` — `nvd.cve.get` CVE-2024-21762 + `cisa_kev.feed.get` count=1647 @ `2026-07-16T18:55:22Z` |

Prod tip SHA at tip time: `8aafb30c…` (STA-303 / Salesforce.query not yet on Railway until merge+deploy).
