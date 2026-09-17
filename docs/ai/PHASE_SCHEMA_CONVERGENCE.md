# Schema convergence (audit §34 item 7)

**Status:** STRUCTURAL — F1 READ slice + HubSpot search class  
**Date:** 2026-09-17

## Contract

One `ActionSpec` owns the advertised schema:

| Consumer | Reads |
|----------|--------|
| ReAct / catalog `inputSchema` | `ActionSpec.input_schema` via `resolve_action_schema` |
| Chat / workflow gate | `ActionSpec.workflow_schema` via `get_workflow_schema` (before batch files) |
| Executor | Must accept calls the advertised schema invites (HubSpot search: query-only or empty → list fallback) |

User-facing JSON/workflow `required` is **not** the same as API-required. Fields with compile sources (`RESOURCE_RESOLVER`, `TIME_RESOLVER`, `ACTION_DEFAULT`, …) stay on `required_parameters` + preflight and are omitted from `required: []` so the model is not asked for a GA4 property id the resolver already has.

## Slice

- F1 five READ keys (overlay unchanged; no new F1 actions).
- HubSpot `contacts|companies|deals|tickets.search` (dead-end class).
- Not a 732-action rewrite. Writes / G8 untouched.

## Evidence

Local: `python -m pytest tests/connectors/action_catalog/test_schema_convergence.py tests/services/test_hubspot_search_honors_advertised_schema.py tests/connectors/action_catalog/test_action_schema.py`
