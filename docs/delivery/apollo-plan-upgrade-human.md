# Apollo plan upgrade (human-only)

**Status:** Blocker for full Phase 4 Sales E2E discover step (`apollo.people.search`).  
**Not agent-actionable** — Cesar / ops must change the Apollo account or connector secrets.

## Evidence

Smoke org Apollo connector is OAuth-only on Apollo **free plan**. Live 403:

`api/v1/mixed_people/api_search is not accessible with this access token on a free plan`

Same class of error for `mixed_companies/search`. Artifact: `docs/delivery/phase4-sales-workflow-e2e-live.json`.

## Options (pick one)

1. **Upgrade** the smoke-org Apollo subscription so OAuth People API Search is allowed.
2. Add a **master API key** on connector `30f734a2-dbdb-45aa-9112-19c6d604d451` (`api_token` / `api_key` secret). Runtime prefers `X-Api-Key` over OAuth when present.

## Already shipped in code

- Free-plan 403 → `permission_denied` (`apollo_plan_limit`), not `auth_expired`
- Prefer master API key over OAuth bearer when both exist
- Health probe no longer uses people search for credential checks

## After human change

Re-run: `python scripts/smoke-phase4-sales-workflow-e2e-live.py`  
Expect `apollo.people.search` success + existing HubSpot `lists.create` PASS for full Phase 4 chain.

Phase 5 ML remains **HELD**.
