# Phase 1 pre-prod gate — migration readiness

**Date:** 2026-07-13  
**Decision requested:** Option A apply + PR (merge held for live stub trace)

## 1. Local vs staging

| Claim | Evidence |
|-------|----------|
| “15 tests PASS” | **Local only** — `pytest tests/intelligence_packs/` on developer machine |
| Staging environment | **No dedicated staging API** used for this slice (org multi-env exists; no separate staging Railway tip for connector-category smoke) |

**Justification for prod apply after fix:** migration is constraint-widening only (see §2). Live stub install on prod smoke org is the post-apply evidence bar (not “local = Done”).

## 2. Additive / reversible / existing connectors

| Change | Nature |
|--------|--------|
| `connectors_status_check` | **Additive** — adds `needs_connection` to existing status list; all prior statuses remain valid |
| `connectors_type_check` | **Additive** — adds intel/BYO types; **must retain every existing type including `pipedrive`** |
| `auth_mode` | **Not a DB column** — catalog/config only; no ALTER of connector rows |

**Regression risk found before apply:** first draft of `20260713140000` **omitted `pipedrive`** (present on prod via `20260626120000`). Applying that draft would have **broken** existing Pipedrive connectors. **Fixed before Option A** — `pipedrive` restored in the migration file.

**Reversibility:** DROP/ADD CHECK can be rolled back by restoring prior constraint defs from prod snapshot (status list without `needs_connection`; type list without new intel types). No data migration / no column drops.

**Pre-existing connector types on prod (verified via `pg_constraint`):** include `apollo`, `hubspot`, `pipedrive`, `slack`, … — all retained after fix.

## 3. BYO fail-closed vs schema

BYO enforcement lives in `backend/app/intelligence_packs/shared/auth_mode.py` (code catalog), **not** in the migration. Schema apply does not change BYO logic.

**Post-migration plan:** re-run `pytest tests/intelligence_packs/test_auth_mode_and_stubs.py` after apply (same suite), plus **live** template install that stages `zoominfo` / `linkedin_sales_navigator` as `needs_connection` with `config.auth_mode=byo_required` and zero `active` rows created.

## Gate verdict

| Gate | Verdict |
|------|---------|
| 1 Local vs staging | Local tests only — proceed with **low-risk additive** justification + **mandatory live stub trace** before merge |
| 2 Additive / no regress | **PASS after pipedrive fix** |
| 3 BYO post-migration | Code-level; reconfirm via pytest + live BYO stub staging |

**Option A authorized on this basis** (user conditional met after pipedrive fix).
