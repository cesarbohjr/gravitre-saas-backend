# Phase 5 — F7 entry-point traces (agent jobs + webhooks)

**Date:** 2026-08-05  
**Status:** CONFIRMED traces (code-path). Live prod re-run not required for “not NL-routed” contracts.

## Agent jobs (`operators/agent_jobs.py`)

| Question | Result |
|----------|--------|
| Path | Queue row → in-process worker → governed `ModelRouter` (not `apply_unified_turn_live`) |
| Plan generation | Model/tool loop may generate steps — **not** chat LIVE retrieve-before-generate |
| `finalize_execution_outcome` | **PARTIAL / path-dependent** — operator/agent completions that create `workflow_run` rows use Module A finalize via execution engine; bare ModelRouter text jobs may not |
| Effect honesty | When execution goes through `workflows/execute.py` / `execution_engine_runtime.py`, `apply_connector_run_honesty` + population verify apply. Pure LLM answers without tool invoke: N/A |
| Exception | **NAMED:** `agent_job_modelrouter_text` — durable operator jobs that never invoke connectors are intentionally outside NL retrieve-before-generate. Connector-bearing jobs should use workflow/tool invoke paths that share finalize. |

**Action taken:** Documented. F1 retrieve gate is enforced on A1/A2/A5d (chat). Agent-job connector work that stages chat-equivalent NL should enter chat/streaming or workflow execute — not a second inventing planner.

## Webhooks

| Entry | NL routing? | LIVE? | Plan generate? | Contract |
|-------|-------------|-------|----------------|----------|
| HubSpot inbound (`/api/webhooks/hubspot`) | No | No | No | **not NL-routed** — event → trigger/service handlers |
| Salesforce inbound | No | No | No | **not NL-routed** |
| PagerDuty inbound | No | No | No | **not NL-routed** |
| Stripe | Billing only | No | No | Out of scope (explicit) |

**F1 applicability:** N/A — no message→plan generation on these paths.

## Closure

F7 UNKNOWN from the standing map is replaced by the contracts above.
