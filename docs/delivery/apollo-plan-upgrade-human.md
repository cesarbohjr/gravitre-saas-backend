# Apollo plan upgrade (BYO — bypassed for platform smoke)

**Status (2026-07-13):** **Bypassed for Phase 4 PARTIAL acceptance.**  
Smoke-org Apollo free-plan 403 is **not** a platform blocker. Users add their own Apollo account API keys (upgraded plan) via connector secrets — `customer_owned` auth.

## Product decision

- Gravitre does **not** require a platform master Apollo key for Phase 4 / Sales pack demos.
- Tenants who need People/Company search bring an upgraded Apollo plan + API key on their connector.
- Runtime already prefers connector `api_token` / `api_key` over OAuth when both exist; free-plan 403 maps to `permission_denied` (`apollo_plan_limit`).

## Evidence (historical)

Smoke org Apollo connector was OAuth-only on Apollo **free plan**. Live 403:

`api/v1/mixed_people/api_search is not accessible with this access token on a free plan`

Artifact: `docs/delivery/phase4-sales-workflow-e2e-live.json`. Phase 4 E2E accepted **PARTIAL**.

## Optional human path (tenant)

1. Upgrade that tenant’s Apollo subscription so People API Search is allowed, **or**
2. Add an API key on their Apollo connector (`api_token` / `api_key`).

Then re-run: `python scripts/smoke-phase4-sales-workflow-e2e-live.py` for that org.

## Already shipped in code

- Free-plan 403 → `permission_denied` (`apollo_plan_limit`), not `auth_expired`
- Prefer master API key over OAuth bearer when both exist
- Health probe no longer uses people search for credential checks
