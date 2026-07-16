# Phase 1 Batch 1 — HubSpot (2026-07-16)

## Scope

Second connector in approved Batch 1 order (after Apollo).

| Item | Detail |
|------|--------|
| API version | CRM **v3** + associations **v4** — **no bump** |
| New actions | `hubspot.contacts.list`, `hubspot.associations.create` |
| Deferred (Batch 1b) | `companies.create`, `owners.list`, `tickets.get` — need HubSpot app publish + smoke re-auth |
| Chat / ReAct / canvas | **Not granted** |

## Why not companies.create in this PR

Live smoke token returns **403** on `companies.search` / `tickets.search`. Repo `hubspot_oauth.py` already requested `companies.read` + `tickets.write`, but published `app-hsmeta.json` only had contacts/deals/lists — the connected token matches the published app. Expanding companies/owners now would tip as permanent 403, not a real proof.

This PR aligns `app-hsmeta.json` + optional OAuth scopes for Batch 1b; live companies/owners wait on app publish + connector reconnect.

## Batch 1b external dependency (named 2026-07-16)

**Status: PENDING — not submitted/approved on HubSpot’s side.**

| Check | Result |
|-------|--------|
| Repo hsmeta scopes updated | Yes (this PR) |
| `hs project upload` / new build after scope change | **No** |
| Deployed build on HubSpot | **#5** (SUCCESS, **2026-06-23**) — last deploy predates Batch 1 scope edit |
| Live smoke `companies.search` | Still **403** on smoke token |

Batch 1b (`companies.create` / `owners.list` / `tickets.get`) is blocked on an **external app-publish timeline** (upload → deploy → smoke connector re-auth), not engineering. Same class as earlier FRED_API_KEY / Apollo plan-tier waits — do not schedule as “next coding PR” until Cesar (or operator) completes HubSpot portal republish.

## Evidence

- Live tip: [`docs/delivery/phase1-hubspot-batch1-live.json`](./phase1-hubspot-batch1-live.json)
- Smoke connector: `547cdda5-2637-4a2b-b087-d5ea89486575`
- Output schema: `hubspot.associations.create` added to `VERIFIED_OUTPUT_BATCH_08`
- `hubspot.contacts.delete` still requires write approval; associations.create does not

## Governance

- Finance/HR live-activation **HOLD** — unchanged
- Chat access deferred until tip review
