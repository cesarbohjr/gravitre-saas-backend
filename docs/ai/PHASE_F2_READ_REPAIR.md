# Phase F2 — READ repair / retry / fallback from PreflightResult

**Status:** structural (local). Does not expand the F1 ActionSpec slice. Does not change WRITE governance or G8.  
**Date:** 2026-09-17

See `docs/ai/PHASE_DOMAIN_PROPERTY_BINDING.md` for audit §34 item 3 (org profile → unique GA4/GSC bind).

One repair attempt after a blocked F1 `PreflightResult`. Invalid provider invocation remains forbidden. Listing fallback uses `hubspot.deals.list` **outside** the F1 proof (that action is not in the F1 slice). GA4 auth blocks may fall back to Search Console only when GSC is connected **and** GSC preflight is ready (HMAC-bound invoke).

| Block | Repair | Bound? |
|---|---|---|
| `WRONG_SIBLING_ACTION` on `hubspot.deals.search` + listing language without structured criteria | Reinvoke `hubspot.deals.list` | No F1 proof (not in slice) |
| GA4 `AUTH_EXPIRED` / `NOT_AUTHENTICATED` / `NOT_CONFIGURED` / `ACTION_UNAVAILABLE` + GSC connected | Preflight + invoke GSC `searchAnalytics.query` | Yes, GSC proof |
| Structured HubSpot search (`high-value`, amount, stage, …) | None — keep original block | — |

ReAct observation statuses: `preflight_blocked`, `repaired`, `repair_failed`.
