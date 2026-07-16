# Phase 1 Batch 1b — HubSpot companies / owners / tickets (2026-07-16)

## Scope

Deferred from HubSpot Batch 1 (#142); unblocked after app build #8 + oauth optional `tickets` (#148) + smoke reconnect.

| Item | Detail |
|------|--------|
| API version | CRM **v3** — **no bump** |
| New actions | `hubspot.companies.create`, `hubspot.owners.list`, `hubspot.tickets.get` |
| Chat / ReAct / canvas | **Not granted** |

## Tip — **PASS** (2026-07-16)

Live evidence: [`phase1-hubspot-batch1b-live.json`](./phase1-hubspot-batch1b-live.json)

| Check | Result |
|-------|--------|
| Prod tip | `f82774f4` (#149) |
| Scopes | companies.read/write, owners.read, tickets granted |
| `companies.create` | success + result_url |
| `owners.list` | success + result_url |
| `tickets.get` | skipped (no ticket rows); `tickets` scope present |

## Governance

- Finance/HR live-activation **HOLD** — unchanged
- Chat access deferred until tip review

## Next

GitHub (one connector per PR), same expansion bar.
