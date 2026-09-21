# HubSpot LIVE fallthrough + unsupported business answer — root cause

**Date:** 2026-09-21  
**Production SHA at discovery:** `909474febb44c058044a414ed8e614a1903a6735` (not `22c59fae`)  
**Isolated org conversation:** `c0980fbc-a36b-4ccf-9c3e-9c5101e31532`  
**This is not a 2.0 COMPLETE declaration.**

## What happened

Natural language: “Show my deals.”

- HubSpot was **executable** on the isolated kernel org.
- Unified LIVE proposed **`hubspot.deals.list`** (`unified_turn.live.fallthrough` `2391a524-acc`, `fallthrough_reason=read_tool_classical`, `live_served=false`).
- Plan step `read_sales_pipeline_health` existed with that action key and stayed **pending**.
- Composer emitted canned “Found **25 deals**” (`response.composer.completed` `5dc47f8d-c95`, `kind=canned`).
- **Zero** `tool.invoke.*` rows. `recent_connector_invocations` empty.

A plausible CRM count is not a completed READ.

## First failing stage

**LIVE-to-classical handoff after a compiled operational READ proposal.**

Unified LIVE is enabled in production. It is skipped only for `analytics_short_circuit`. Pipeline/deals recipes still entered LIVE, which 1) proposed `hubspot.deals.list`, 2) returned `None` (`read_tool_classical`), 3) did not transfer a verified Observation into Composer. Classical `try_compiled_operational_read_turn` at `react_entry` was supposed to execute the sealed F1 path; the surviving plan step remained pending and Composer still received a business-looking canned draft. The ActionSpec default **limit=25** matches the invented count class.

## Capability / action

| Question | Finding |
|---|---|
| Is `hubspot.deals.list` a valid catalog action? | **Yes** — F1 slice, ActionSpec, `crm.deals.read` / `sales.pipeline.health` |
| Implemented? | **Yes** — `_exec_hubspot_deals_list` in `tool_service.py` |
| Eligible under compiled capability? | **Yes** — open-ended `crm.deals.read` uses **list**, not search |
| Is `hubspot.deals.search` intended instead? | **No** for open-ended “show my deals.” Search without criteria is `WRONG_SIBLING_ACTION` (preserved) |
| ActionSpec → adapter | `execution_adapter: hubspot.deals.list` |
| Does LIVE fall through on this READ? | **Yes** — by design for connector tool proposals; it must not *serve* the READ |
| Does classical receive the same compiled action? | Recipe resolver still maps `hubspot.deals.search` → `hubspot.deals.list` for open-ended asks (sibling protection, not a silent unrelated swap) |
| Silent replace with a different system? | Website follow-ups could be rewritten toward HubSpot by Composer because the website frame was not stored when GA/GSC were not executable |

## LIVE / classical handoff

`apply_unified_turn_live` returns `None` on `read_tool_classical`. No plan_id / preflight / observation is attached. Composer can still `kind=canned` with `success` implied by draft. That is illegal for provider-derived claims.

**Fix:** skip Unified LIVE when `should_skip_unified_live_for_compiled_read` (analytics short-circuit, operational F1 recipes, or existing website frame). Execute sealed HMAC at `react_entry`. Persist Observation + `provider_result_evidence`. Composer strips ungrounded counts.

## Provider invocation

Missing `tool.invoke.completed` is **not** proof the provider was never called: sealed F1 used actor_id `operational-f1-read`, which **cannot insert** `audit_events` (`actor_id` UUID NOT NULL / FK `auth.users`). Durable evidence must be Observation + HMAC invoke result, with audit when the requesting user UUID is used as actor.

## Audit identity

- Do **not** mint a random UUID.
- Do **not** impersonate the operator org.
- Canonical actor: **authenticated requesting user UUID** (`execution_actor_source=authenticated_user`).
- If no UUID is available (unit tests / mis-bound context), keep the non-UUID label; audit is skipped; **Observation in task_state is the durable evidence contract**. Audit skip must not be reported as success.

## Grounding defect

Composer treated canned rewrite of a limit/proposal as a completed business result. Correction: `provider_result_grounding.apply_provider_result_grounding` — no deal/invoice/ticket/traffic/revenue/workflow count without `provider_result_evidence`.

## Source selection / continuity

Isolated GA `pending_auth`, GSC `token_expired`. Connect-guidance did not store a website `active_analysis`, so “Show last week instead.” left the website objective and Composer offered CRM. Fix: store website frame; limitation copy names Analytics/GSC readiness only; HubSpot is not a website fallback.

## Rollback

Revert the grounding + skip-LIVE + actor UUID + website-frame commit. Unified LIVE and Composer behavior return to prior; do not roll back HMAC/write-gate commits.
