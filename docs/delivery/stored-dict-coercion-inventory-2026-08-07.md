# Stored dict coercion inventory (Phase 1)

Snapshot source: `HEAD` (pre-refactor baseline before this pass).

## Summary

- Total dict coercion candidates with `.get(...)` or subscript input: **423**
- `.get(...)` candidates: **194**
- Subscript candidates: **229**
- Classified `legacy-shape-reachable`: **167**
- Classified `reviewed-safe-or-local`: **41**
- Classified `likely-safe-row-copy`: **215**

## Complete inventory

| File | Line | Pattern | Risk class | Expression | Rationale |
|---|---:|---|---|---|---|
| `backend/app/billing/service.py` | 198 | `dict-get` | `reviewed-safe-or-local` | `DEFAULT_PLANS.get(code) or DEFAULT_PLANS[DEFAULT_PLAN_CODE]` | non-stored key access; still matched global pattern |
| `backend/app/billing/service.py` | 203 | `dict-get` | `legacy-shape-reachable` | `template.get("features") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/billing/service.py` | 284 | `dict-subscript` | `likely-safe-row-copy` | `row[0]` | row-copy/index conversion from query response structures |
| `backend/app/billing/service.py` | 329 | `dict-subscript` | `likely-safe-row-copy` | `row[0]` | row-copy/index conversion from query response structures |
| `backend/app/billing/service.py` | 365 | `dict-get` | `legacy-shape-reachable` | `merged.get("features") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/billing/service.py` | 397 | `dict-subscript` | `likely-safe-row-copy` | `created.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/action_catalog/schema_generator.py` | 328 | `dict-get` | `reviewed-safe-or-local` | `schema.get("properties") or {}` | non-stored key access; still matched global pattern |
| `backend/app/connectors/apollo_api.py` | 77 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/clay_api.py` | 36 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/clay_api.py` | 60 | `dict-get` | `legacy-shape-reachable` | `conn.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/confluence_oauth.py` | 139 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/confluence_oauth.py` | 215 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/generic_oauth.py` | 318 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/generic_oauth.py` | 343 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_ads_oauth.py` | 39 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_analytics_oauth.py` | 137 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_analytics_oauth.py` | 159 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_analytics_oauth.py` | 166 | `dict-get` | `reviewed-safe-or-local` | `config.get("health") or {}` | non-stored key access; still matched global pattern |
| `backend/app/connectors/google_analytics_oauth.py` | 236 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_calendar_oauth.py` | 158 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_search_console_oauth.py` | 39 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_vendor_oauth.py` | 193 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_vendor_oauth.py` | 207 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_vendor_oauth.py` | 252 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/google_vendor_oauth.py` | 369 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/health_monitor_service.py` | 92 | `dict-get` | `legacy-shape-reachable` | `row.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/hubspot_oauth.py` | 218 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/hubspot_oauth.py` | 244 | `dict-get` | `legacy-shape-reachable` | `row.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/jira_oauth.py` | 203 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/jira_oauth.py` | 279 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/marketo_oauth.py` | 128 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/marketo_oauth.py` | 171 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/marketo_oauth.py` | 224 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/marketo_oauth.py` | 250 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/netsuite_oauth.py` | 231 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/netsuite_oauth.py` | 289 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/notion_oauth.py` | 163 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/pagerduty.py` | 82 | `dict-get` | `reviewed-safe-or-local` | `data.get("user") or data` | non-stored key access; still matched global pattern |
| `backend/app/connectors/pagerduty.py` | 87 | `dict-get` | `reviewed-safe-or-local` | `data.get("incident") or data` | non-stored key access; still matched global pattern |
| `backend/app/connectors/pagerduty_oauth.py` | 224 | `dict-get` | `reviewed-safe-or-local` | `result.get("webhook_subscription") or result` | non-stored key access; still matched global pattern |
| `backend/app/connectors/pagerduty_oauth.py` | 276 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/plaid_link.py` | 190 | `dict-subscript` | `likely-safe-row-copy` | `rows.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/quickbooks_oauth.py` | 212 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/quickbooks_oauth.py` | 282 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/repository.py` | 107 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/repository.py` | 130 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/repository.py` | 160 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/repository.py` | 190 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/repository.py` | 215 | `dict-get` | `legacy-shape-reachable` | `connector.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/salesforce_oauth.py` | 263 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/salesforce_oauth.py` | 305 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/segment_api.py` | 42 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/segment_connect.py` | 34 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/slack_oauth.py` | 163 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/stripe_api.py` | 54 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/connectors/workday_oauth.py` | 225 | `dict-get` | `legacy-shape-reachable` | `(row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/workday_oauth.py` | 247 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/connectors/workday_oauth.py` | 359 | `dict-get` | `legacy-shape-reachable` | `(existing.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 14 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 41 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 75 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 105 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 133 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/mappers.py` | 163 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/normalize.py` | 55 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/pipeline.py` | 71 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/provenance.py` | 29 | `dict-get` | `legacy-shape-reachable` | `record.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/intelligence_packs/shared/signals.py` | 63 | `dict-get` | `legacy-shape-reachable` | `record.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/marketplace/adoption.py` | 94 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/browse.py` | 384 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/clone.py` | 110 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/convergence.py` | 188 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [{"id": existing_id}])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/convergence.py` | 195 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/crud.py` | 64 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/crud.py` | 277 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/crud.py` | 442 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/entitlements.py` | 54 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/entitlements.py` | 168 | `dict-subscript` | `likely-safe-row-copy` | `(inserted.data or [pending])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/entitlements.py` | 258 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/payouts.py` | 85 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/publishers.py` | 72 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/publishers.py` | 101 | `dict-subscript` | `likely-safe-row-copy` | `existing.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/publishers.py` | 133 | `dict-subscript` | `likely-safe-row-copy` | `(refreshed.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/publishers.py` | 156 | `dict-subscript` | `likely-safe-row-copy` | `(refreshed.data or [{"id": publisher_id}])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/service.py` | 316 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/service.py` | 407 | `dict-subscript` | `legacy-shape-reachable` | `step["config"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/marketplace/service.py` | 412 | `dict-subscript` | `legacy-shape-reachable` | `step["metadata"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/marketplace/service.py` | 1367 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/support.py` | 344 | `dict-get` | `legacy-shape-reachable` | `install_row.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/marketplace/support.py` | 420 | `dict-subscript` | `likely-safe-row-copy` | `mine.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/support.py` | 461 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/support.py` | 532 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/versions.py` | 44 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/versions.py` | 75 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/marketplace/workflow_contract.py` | 21 | `dict-get` | `legacy-shape-reachable` | `row.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/middleware/entitlements.py` | 116 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/middleware/entitlements.py` | 188 | `dict-get` | `reviewed-safe-or-local` | `TIER_LIMITS.get(tier, TIER_LIMITS["free"])` | non-stored key access; still matched global pattern |
| `backend/app/middleware/entitlements.py` | 190 | `dict-get` | `reviewed-safe-or-local` | `TIER_FEATURES.get(tier, TIER_FEATURES["free"])` | non-stored key access; still matched global pattern |
| `backend/app/operators/agent_intelligence.py` | 286 | `dict-get` | `legacy-shape-reachable` | `operator.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/operators/repository.py` | 47 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 109 | `dict-subscript` | `likely-safe-row-copy` | `(r.data or existing.data)[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 115 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 193 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 315 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 348 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 383 | `dict-subscript` | `likely-safe-row-copy` | `v.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 512 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 526 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 575 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 590 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 644 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/repository.py` | 709 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/operators/services/auto_execute_service.py` | 153 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 271 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 312 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 334 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 373 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 424 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 530 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/ingest.py` | 578 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/rag/rerank_eval.py` | 144 | `dict-subscript` | `likely-safe-row-copy` | `rows[idx]` | row-copy/index conversion from query response structures |
| `backend/app/routers/audit.py` | 333 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/auth.py` | 145 | `dict-subscript` | `likely-safe-row-copy` | `user_resp.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/confluence_sync.py` | 54 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/connector_oauth.py` | 555 | `dict-subscript` | `likely-safe-row-copy` | `existing_cfg.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/connector_oauth.py` | 617 | `dict-get` | `legacy-shape-reachable` | `(connector_row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/connector_oauth.py` | 708 | `dict-get` | `legacy-shape-reachable` | `(connector_row.data or [{}])[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/enterprise.py` | 184 | `dict-get` | `legacy-shape-reachable` | `org_settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/enterprise.py` | 754 | `dict-get` | `legacy-shape-reachable` | `org_settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/google_ads.py` | 38 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/google_ads.py` | 73 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/google_analytics.py` | 38 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/google_analytics.py` | 67 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/google_search_console.py` | 37 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/google_search_console.py` | 63 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/routers/hubspot_triggers.py` | 57 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/knowledge_sync.py` | 181 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/marketplace.py` | 1057 | `dict-subscript` | `likely-safe-row-copy` | `registry.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/notion_sync.py` | 53 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/pagerduty_triggers.py` | 55 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/pagerduty_triggers.py` | 89 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/salesforce_triggers.py` | 59 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 116 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 237 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 267 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 293 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 315 | `dict-subscript` | `likely-safe-row-copy` | `existing.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 333 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 403 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 429 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 455 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/scim.py` | 495 | `dict-subscript` | `likely-safe-row-copy` | `refreshed.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/segment_triggers.py` | 58 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/segment_triggers.py` | 93 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 116 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 147 | `dict-subscript` | `likely-safe-row-copy` | `(response.data or [{}])[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 271 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 302 | `dict-subscript` | `likely-safe-row-copy` | `(response.data or [{}])[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 333 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 374 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 404 | `dict-subscript` | `likely-safe-row-copy` | `(response.data or [{}])[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/training.py` | 435 | `dict-subscript` | `likely-safe-row-copy` | `response.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/webhooks/pagerduty_inbound.py` | 44 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/webhooks/salesforce_inbound.py` | 41 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/webhooks/segment_inbound.py` | 46 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/webhooks/workflow_triggers.py` | 74 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/workday_sync.py` | 53 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/workflows.py` | 4290 | `dict-subscript` | `likely-safe-row-copy` | `created.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/workflows.py` | 4437 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/routers/workflows.py` | 4486 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/samples/stripe_connect_v2/store.py` | 57 | `dict-get` | `reviewed-safe-or-local` | `_read(store_path).get("sellers") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/adaptive_learning_service.py` | 157 | `dict-get` | `reviewed-safe-or-local` | `state.get("assignment_boost_deltas") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/adaptive_learning_service.py` | 158 | `dict-get` | `reviewed-safe-or-local` | `state.get("source_weight_deltas") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/agent_finetune_service.py` | 183 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/agent_interrupt_service.py` | 114 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/agent_interrupt_service.py` | 191 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/agent_knowledge_assignment_service.py` | 445 | `dict-get` | `legacy-shape-reachable` | `agent.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/agent_role_marketplace_service.py` | 163 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/agent_role_marketplace_service.py` | 260 | `dict-subscript` | `legacy-shape-reachable` | `step["config"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/agent_role_marketplace_service.py` | 265 | `dict-subscript` | `legacy-shape-reachable` | `step["metadata"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/agent_role_marketplace_service.py` | 478 | `dict-subscript` | `likely-safe-row-copy` | `(result.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/assistant_routing_tier.py` | 254 | `dict-subscript` | `likely-safe-row-copy` | `LATENCY_BUDGETS[tier]` | row-copy/index conversion from query response structures |
| `backend/app/services/assistant_tools.py` | 583 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/assistant_tools.py` | 773 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/autonomous_budget_service.py` | 301 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/autonomous_budget_service.py` | 373 | `dict-get` | `legacy-shape-reachable` | `settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/autonomous_budget_service.py` | 374 | `dict-get` | `reviewed-safe-or-local` | `enterprise.get("autonomousRunBudgets") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/b2b_handoff_service.py` | 119 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 151 | `dict-subscript` | `likely-safe-row-copy` | `existing.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 173 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 229 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [partnership])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 262 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [partnership])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 295 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [partnership])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 321 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 371 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 430 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 452 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 471 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [handoff])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 501 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 513 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [handoff])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 542 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/b2b_handoff_service.py` | 555 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [handoff])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/branding_service.py` | 30 | `dict-get` | `legacy-shape-reachable` | `settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/branding_service.py` | 31 | `dict-get` | `legacy-shape-reachable` | `enterprise.get("branding") or DEFAULT_BRANDING` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/branding_service.py` | 47 | `dict-get` | `legacy-shape-reachable` | `settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/branding_service.py` | 48 | `dict-get` | `legacy-shape-reachable` | `enterprise.get("branding") or DEFAULT_BRANDING` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/branding_service.py` | 58 | `dict-get` | `legacy-shape-reachable` | `settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/branding_service.py` | 59 | `dict-get` | `legacy-shape-reachable` | `enterprise.get("branding") or DEFAULT_BRANDING` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/canvas_write_gate.py` | 154 | `dict-subscript` | `likely-safe-row-copy` | `rows.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/chat_connector_execution_service.py` | 894 | `dict-get` | `legacy-shape-reachable` | `payload.get("inference_sources") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_connector_execution_service.py` | 2179 | `dict-get` | `legacy-shape-reachable` | `serialized.get("structured") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_e2e_scenarios.py` | 309 | `dict-get` | `legacy-shape-reachable` | `pre_turn.get("task_state") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1108 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1173 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1433 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1798 | `dict-get` | `reviewed-safe-or-local` | `task_state.get("pending_task") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/chat_orchestration_service.py` | 1799 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or pending.get("params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1814 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 1911 | `dict-get` | `legacy-shape-reachable` | `(task_state.get("clarified_params") or {})             or ((task_state.get("pending_task") or {}).get("params") or {})` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_orchestration_service.py` | 2065 | `dict-get` | `legacy-shape-reachable` | `row.get("structured") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_workflow_e2e_live.py` | 235 | `dict-get` | `reviewed-safe-or-local` | `args.get("properties") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/chat_workflow_e2e_live.py` | 247 | `dict-get` | `legacy-shape-reachable` | `args.get("payload") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/chat_workflow_e2e_scenarios.py` | 267 | `dict-get` | `legacy-shape-reachable` | `turn.get("task_state") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/clay_tools.py` | 120 | `dict-subscript` | `legacy-shape-reachable` | `params["payload"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/compensation_service.py` | 69 | `dict-get` | `reviewed-safe-or-local` | `row.get("properties") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/compensation_service.py` | 77 | `dict-get` | `reviewed-safe-or-local` | `row.get("properties") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/compensation_service.py` | 207 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/confluence_sync_service.py` | 77 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/confluence_sync_service.py` | 78 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/confluence_sync_service.py` | 111 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/confluence_sync_service.py` | 207 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/confluence_sync_service.py` | 256 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/connector_fixture_service.py` | 70 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/connector_fixture_service.py` | 121 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/connector_fixture_service.py` | 128 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/connector_fixture_service.py` | 152 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/connector_session_state.py` | 92 | `dict-subscript` | `legacy-shape-reachable` | `payload["pendingApproval"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/connector_session_state.py` | 323 | `dict-get` | `legacy-shape-reachable` | `row.get("structured") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/conversation_memory_engine.py` | 80 | `dict-get` | `legacy-shape-reachable` | `memory.get("preferences") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/conversation_state_service.py` | 137 | `dict-get` | `reviewed-safe-or-local` | `current_ledger.get("slots") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/conversation_state_service.py` | 142 | `dict-get` | `reviewed-safe-or-local` | `value.get("slots") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/conversation_turn_controller.py` | 656 | `dict-get` | `legacy-shape-reachable` | `cfg.get("params") or cfg.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/conversational_execution_service.py` | 331 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/conversational_execution_service.py` | 334 | `dict-subscript` | `legacy-shape-reachable` | `pending_early["params"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/conversational_execution_service.py` | 437 | `dict-get` | `legacy-shape-reachable` | `task_state.get("clarified_params") or pending.get("params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/cross_org_delegated_task_service.py` | 89 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 155 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 273 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 317 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 359 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 403 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 458 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/cross_org_delegated_task_service.py` | 503 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [task])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/devops_workflow_service.py` | 286 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/domain_routing_policy.py` | 82 | `dict-get` | `reviewed-safe-or-local` | `updated.get("persona") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/engagebay_tools.py` | 71 | `dict-get` | `reviewed-safe-or-local` | `params.get("properties") or params` | non-stored key access; still matched global pattern |
| `backend/app/services/engagebay_tools.py` | 90 | `dict-get` | `reviewed-safe-or-local` | `params.get("properties") or params` | non-stored key access; still matched global pattern |
| `backend/app/services/extension_bridge_service.py` | 677 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/extension_bridge_service.py` | 690 | `dict-get` | `legacy-shape-reachable` | `context.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/extension_bridge_service.py` | 1057 | `dict-get` | `legacy-shape-reachable` | `pending.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/federated_connector_service.py` | 111 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 156 | `dict-subscript` | `likely-safe-row-copy` | `row[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 206 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 282 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [grant])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 316 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [grant])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 350 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [grant])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/federated_connector_service.py` | 382 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/gravitre_connector_activation.py` | 84 | `dict-get` | `legacy-shape-reachable` | `conn.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/handoff_service.py` | 58 | `dict-subscript` | `reviewed-safe-or-local` | `parameters["decision"]` | string-key subscript not on persisted-shape field |
| `backend/app/services/handoff_service.py` | 60 | `dict-subscript` | `reviewed-safe-or-local` | `source_output["decision"]` | string-key subscript not on persisted-shape field |
| `backend/app/services/handoff_service.py` | 102 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/handoff_service.py` | 130 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/healthcare_vertical_service.py` | 356 | `dict-get` | `legacy-shape-reachable` | `(org_row.data or [{}])[0].get("settings") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hipaa_service.py` | 99 | `dict-get` | `legacy-shape-reachable` | `org.get("settings") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hipaa_service.py` | 100 | `dict-get` | `legacy-shape-reachable` | `org_settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hipaa_service.py` | 141 | `dict-get` | `legacy-shape-reachable` | `org.get("settings") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hipaa_service.py` | 142 | `dict-get` | `legacy-shape-reachable` | `org_settings.get("enterprise") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hipaa_service.py` | 194 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/hubspot_knowledge_sync_service.py` | 56 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hubspot_knowledge_sync_service.py` | 145 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/hubspot_knowledge_sync_service.py` | 160 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hubspot_trigger_service.py` | 154 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/hubspot_trigger_service.py` | 171 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/hubspot_trigger_service.py` | 393 | `dict-subscript` | `likely-safe-row-copy` | `existing_row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/integration_suggestion_service.py` | 579 | `dict-subscript` | `likely-safe-row-copy` | `created.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/integration_suggestion_service.py` | 656 | `dict-subscript` | `likely-safe-row-copy` | `created.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/integration_suggestion_service.py` | 722 | `dict-get` | `legacy-shape-reachable` | `row.get("evidence") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/integration_suggestion_service.py` | 792 | `dict-get` | `legacy-shape-reachable` | `row.get("evidence") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/integration_suggestion_service.py` | 794 | `dict-get` | `legacy-shape-reachable` | `pending.get("params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/intelligence_pack_tools.py` | 129 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/intelligence_pack_tools.py` | 177 | `dict-get` | `legacy-shape-reachable` | `raw.get("provenance") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/job_workspace_service.py` | 48 | `dict-get` | `legacy-shape-reachable` | `row.get("payload") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/job_workspace_service.py` | 66 | `dict-get` | `reviewed-safe-or-local` | `workspace.get("files") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/job_workspace_service.py` | 80 | `dict-get` | `legacy-shape-reachable` | `(resp.data or {}).get("payload") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/knowledge_source_types.py` | 91 | `dict-get` | `legacy-shape-reachable` | `payload.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/knowledge_source_types.py` | 100 | `dict-get` | `legacy-shape-reachable` | `payload.get("freshness_policy") or payload.get("freshnessPolicy") or metadata.get("freshness_policy") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/knowledge_source_types.py` | 101 | `dict-get` | `legacy-shape-reachable` | `payload.get("permission_policy") or payload.get("permissionPolicy") or metadata.get("permission_policy") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/knowledge_sync_service.py` | 156 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/knowledge_sync_service.py` | 183 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/knowledge_sync_service.py` | 473 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/legal_vertical_service.py` | 365 | `dict-get` | `legacy-shape-reachable` | `(org_row.data or [{}])[0].get("settings") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/mcp_client_service.py` | 277 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/mcp_client_service.py` | 299 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/meson_service.py` | 545 | `dict-subscript` | `likely-safe-row-copy` | `created.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/meta_learning_service.py` | 101 | `dict-get` | `reviewed-safe-or-local` | `state.get("meta_learning_state") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/meta_learning_service.py` | 102 | `dict-get` | `reviewed-safe-or-local` | `meta_state.get(family) or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/meta_learning_service.py` | 103 | `dict-get` | `reviewed-safe-or-local` | `family_bucket.get(key) or {"wins": 0, "losses": 0, "neutral": 0, "samples": 0}` | non-stored key access; still matched global pattern |
| `backend/app/services/mode_b_feedback_service.py` | 261 | `dict-get` | `legacy-shape-reachable` | `agent.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/notification_emitter.py` | 92 | `dict-get` | `reviewed-safe-or-local` | `ref.get("activity_metadata") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/notification_emitter.py` | 169 | `dict-get` | `reviewed-safe-or-local` | `entity_ref.get("activity_metadata") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/notion_sync_service.py` | 77 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/notion_sync_service.py` | 78 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/notion_sync_service.py` | 109 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/notion_sync_service.py` | 209 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/notion_sync_service.py` | 257 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/optimization_suggestion_service.py` | 743 | `dict-get` | `legacy-shape-reachable` | `rows[0].get("evidence") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/optimization_suggestion_service.py` | 811 | `dict-get` | `legacy-shape-reachable` | `node.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/optimization_suggestion_service.py` | 818 | `dict-get` | `legacy-shape-reachable` | `suggestion.get("evidence") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/optimization_suggestion_service.py` | 859 | `dict-get` | `legacy-shape-reachable` | `suggestion.get("evidence") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/optimization_suggestion_service.py` | 873 | `dict-get` | `reviewed-safe-or-local` | `preview.get("before_config") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/optimization_suggestion_service.py` | 874 | `dict-get` | `reviewed-safe-or-local` | `preview.get("after_config") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/pagerduty_trigger_service.py` | 63 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/pagerduty_trigger_service.py` | 84 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/pagerduty_trigger_service.py` | 111 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/pagerduty_trigger_service.py` | 216 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/parameter_ledger.py` | 839 | `dict-get` | `legacy-shape-reachable` | `params.get("inference_sources") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/parameter_ledger.py` | 854 | `dict-get` | `legacy-shape-reachable` | `(advanced.get("pending_task") or {}).get("params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/persona_service.py` | 197 | `dict-get` | `reviewed-safe-or-local` | `self.COMMUNICATION_PERSONAS.get(key, self.COMMUNICATION_PERSONAS["friendly_assistant"])` | non-stored key access; still matched global pattern |
| `backend/app/services/post_action_experience_service.py` | 691 | `dict-get` | `legacy-shape-reachable` | `serialized.get("structured") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/rag_service.py` | 113 | `dict-get` | `reviewed-safe-or-local` | `cached_payload.get("metrics") or {}` | non-stored key access; still matched global pattern |
| `backend/app/services/react_write_gate.py` | 218 | `dict-get` | `legacy-shape-reachable` | `call.get("args") or result.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/react_write_gate.py` | 267 | `dict-get` | `legacy-shape-reachable` | `pending.get("args") or result.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/react_write_gate.py` | 328 | `dict-subscript` | `legacy-shape-reachable` | `result["args"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/react_write_gate.py` | 394 | `dict-get` | `legacy-shape-reachable` | `pending.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/react_write_gate.py` | 397 | `dict-subscript` | `legacy-shape-reachable` | `result["args"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/react_write_gate.py` | 531 | `dict-get` | `legacy-shape-reachable` | `pending.get("args") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/real_estate_vertical_service.py` | 339 | `dict-get` | `legacy-shape-reachable` | `(org_row.data or [{}])[0].get("settings") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/salesforce_trigger_service.py` | 61 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/salesforce_trigger_service.py` | 82 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/salesforce_trigger_service.py` | 107 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/salesforce_trigger_service.py` | 241 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/segment_trigger_service.py` | 60 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/segment_trigger_service.py` | 81 | `dict-get` | `legacy-shape-reachable` | `row.data[0].get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/segment_trigger_service.py` | 107 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/segment_trigger_service.py` | 212 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/source_sync_service.py` | 137 | `dict-get` | `legacy-shape-reachable` | `row.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/swarm_coordinator_service.py` | 153 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 292 | `dict-subscript` | `likely-safe-row-copy` | `swarm_insert.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 310 | `dict-subscript` | `likely-safe-row-copy` | `sub_insert.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 337 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [subtask])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 408 | `dict-subscript` | `likely-safe-row-copy` | `(failed.data or [swarm])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 474 | `dict-subscript` | `likely-safe-row-copy` | `(failed.data or [swarm])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 505 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [swarm])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 589 | `dict-subscript` | `likely-safe-row-copy` | `(updated.data or [swarm])[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 616 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/swarm_coordinator_service.py` | 657 | `dict-subscript` | `likely-safe-row-copy` | `swarm.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/task_classifier.py` | 149 | `dict-get` | `reviewed-safe-or-local` | `TASK_TYPE_PIPELINE_MAP.get(intent, TASK_TYPE_PIPELINE_MAP["general"])` | non-stored key access; still matched global pattern |
| `backend/app/services/task_classifier.py` | 153 | `dict-subscript` | `reviewed-safe-or-local` | `TASK_TYPE_PIPELINE_MAP["workflow_planning"]` | string-key subscript not on persisted-shape field |
| `backend/app/services/transparency_service.py` | 225 | `dict-subscript` | `likely-safe-row-copy` | `inserted.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/transparency_service.py` | 271 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/transparency_service.py` | 333 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/transparency_service.py` | 447 | `dict-subscript` | `likely-safe-row-copy` | `rows[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/unified_turn_pending_live.py` | 122 | `dict-get` | `legacy-shape-reachable` | `state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/unified_turn_reasoning_service.py` | 1053 | `dict-get` | `legacy-shape-reachable` | `updated_state.get("clarified_params") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/voice_expression_range.py` | 409 | `dict-subscript` | `legacy-shape-reachable` | `rows.data[0]["task_state"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/workday_sync_service.py` | 77 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/workday_sync_service.py` | 78 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workday_sync_service.py` | 110 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workday_sync_service.py` | 212 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/workday_sync_service.py` | 252 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workflow_failure_prediction_service.py` | 142 | `dict-get` | `legacy-shape-reachable` | `step.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workflow_failure_prediction_service.py` | 143 | `dict-get` | `legacy-shape-reachable` | `step.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workflow_failure_prediction_service.py` | 226 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/workflow_failure_prediction_service.py` | 368 | `dict-subscript` | `legacy-shape-reachable` | `active["definition"]` | string-key stored field coercion can crash on non-dict payloads |
| `backend/app/services/workflow_failure_prediction_service.py` | 687 | `dict-get` | `legacy-shape-reachable` | `step.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/workflow_failure_prediction_service.py` | 800 | `dict-get` | `legacy-shape-reachable` | `row.get("evidence") if isinstance(row.get("evidence"), dict) else {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/zendesk_knowledge_sync_service.py` | 73 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/services/zendesk_knowledge_sync_service.py` | 128 | `dict-subscript` | `likely-safe-row-copy` | `row.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/services/zendesk_knowledge_sync_service.py` | 133 | `dict-get` | `legacy-shape-reachable` | `connector.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/approval_batch_service.py` | 123 | `dict-subscript` | `likely-safe-row-copy` | `(inserted.data or [batch_row])[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/approval_batch_service.py` | 175 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/approval_batch_service.py` | 220 | `dict-subscript` | `likely-safe-row-copy` | `batch_result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/builder_sync.py` | 522 | `dict-get` | `legacy-shape-reachable` | `row.get("metadata") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/builder_sync.py` | 523 | `dict-get` | `legacy-shape-reachable` | `row.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/builder_sync.py` | 995 | `dict-subscript` | `likely-safe-row-copy` | `wf_meta.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/digital_twin.py` | 75 | `dict-get` | `reviewed-safe-or-local` | `fixture.get("response") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/digital_twin.py` | 150 | `dict-get` | `legacy-shape-reachable` | `sdef.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/dry_run.py` | 96 | `dict-get` | `legacy-shape-reachable` | `sdef.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execute.py` | 119 | `dict-get` | `legacy-shape-reachable` | `sdef.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 418 | `dict-get` | `legacy-shape-reachable` | `step_def.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 773 | `dict-get` | `legacy-shape-reachable` | `step.get("config") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1042 | `dict-get` | `reviewed-safe-or-local` | `run.get("parameters") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/execution_engine_runtime.py` | 1053 | `dict-get` | `legacy-shape-reachable` | `checkpoint.get("approval_context") or params.get("approval_context") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1089 | `dict-get` | `legacy-shape-reachable` | `checkpoint.get("node_outputs") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1140 | `dict-get` | `reviewed-safe-or-local` | `run.get("parameters") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/execution_engine_runtime.py` | 1152 | `dict-get` | `legacy-shape-reachable` | `checkpoint.get("approval_context") or params.get("approval_context") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1166 | `dict-get` | `legacy-shape-reachable` | `checkpoint.get("node_outputs") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1244 | `dict-get` | `reviewed-safe-or-local` | `run.get("parameters") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/execution_engine_runtime.py` | 1261 | `dict-get` | `legacy-shape-reachable` | `checkpoint.get("node_outputs") or {}` | stored/serialized field via .get may be str/list/None in legacy rows |
| `backend/app/workflows/execution_engine_runtime.py` | 1327 | `dict-get` | `reviewed-safe-or-local` | `run.get("parameters") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/repository.py` | 48 | `dict-subscript` | `likely-safe-row-copy` | `contract.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 59 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 147 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 193 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 228 | `dict-subscript` | `likely-safe-row-copy` | `v.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 284 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 319 | `dict-get` | `reviewed-safe-or-local` | `(row.data or [{}])[0].get("parameters") or {}` | non-stored key access; still matched global pattern |
| `backend/app/workflows/repository.py` | 386 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 412 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 423 | `dict-subscript` | `likely-safe-row-copy` | `updated.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 434 | `dict-subscript` | `likely-safe-row-copy` | `ins.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 476 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 535 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 582 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 634 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 685 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 745 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 771 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 867 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 905 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/repository.py` | 962 | `dict-subscript` | `likely-safe-row-copy` | `r.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/schema_sync.py` | 302 | `dict-subscript` | `likely-safe-row-copy` | `result.data[0]` | row-copy/index conversion from query response structures |
| `backend/app/workflows/schema_sync.py` | 350 | `dict-subscript` | `likely-safe-row-copy` | `run_result.data[0]` | row-copy/index conversion from query response structures |
