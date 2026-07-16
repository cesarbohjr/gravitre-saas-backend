# Phase 1 Batch 1 — Apollo (2026-07-16)

## Scope

First connector in approved Batch 1 order (Crunchbase skipped / deferred as new integration).

| Item | Detail |
|------|--------|
| API version | `api/v1` — **no bump** |
| New actions | `apollo.people.match` (POST `/people/match`), `apollo.organizations.enrich` (GET `/organizations/enrich`) |
| Already present | search/list/create/update/delete/sequences/enrichment.bulk — left in place |
| Chat / ReAct / canvas | **Not granted** — await tip review |

## Evidence

- Live tip: [`docs/delivery/phase1-apollo-batch1-live.json`](./phase1-apollo-batch1-live.json) — **pass: true**
- Smoke org Apollo connector: `30f734a2-dbdb-45aa-9112-19c6d604d451`
- `apollo.organizations.enrich` — success + `result_url` (`https://app.apollo.io/#/organizations/5e66b638…`)
- `apollo.people.match` — real vendor 403 plan-limit (same class as existing `people.search` free-plan gap); not a wiring miss
- Unit: `test_apollo_tools`, `test_apollo_write_authority`, `test_apollo_api` (match/enrich)

## Governance

- `apollo.contacts.delete` / `apollo.sequences.remove` still require write approval (`catalog_write_authority`)
- Finance/HR action expansion **excluded**
- F3/H3 live-activation **HOLD** (separate Cesar STA-312) — unchanged

## Next

HubSpot (one connector per PR), same expansion bar.
