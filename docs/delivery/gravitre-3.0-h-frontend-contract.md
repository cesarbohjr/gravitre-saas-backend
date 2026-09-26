# Gravitre 3.0-H frontend contract (2026-09-24)

The Gravitre 3.0 Plus frontend agent owns workspace, Window Manager, artifact panel, Intelligence composition, React Flow, and voice visualizers. This file is the **API/SSE/artifact** delta only.

## Unchanged

- Chat SSE event types (`text-delta`, `text`, `[DONE]`).
- `POST /api/assistant/chat` body (`messages`, `org_id`, `mode`, `conversation_id`).
- GET `/api/assistant/conversation/{id}/state` claim_labels from 3.0-F.
- Artifact `kind=report` from 3.0-D/E.

## Added fields (optional; ignore if unused)

On compiled catalog search:

- `execution_path`: `catalog_search_eligible`
- `writes_listed`: integer of discoverable governed WRITE rows
- `include_writes`: true when the user asked for capabilities (not a READ-only catalog search)
- Message text already labels WRITE rows as `WRITE, approval required — not executed`

On store-backed entity answers:

- `execution_path`: `entity_join_store`
- `entity_id`: canonical BusinessEntity id when a join exists
- `systems`: vendor keys from accepted bindings
- `missing_live_sources`: human strings for disconnected OAuth vendors
- `join`: boolean (false means records stay separate)

On listing F2:

- `execution_path`: `listing_f2_read`
- `repaired`: boolean when `hubspot.deals.search` was repaired to `hubspot.deals.list`
- Existing `execution_result` / observation ids unchanged
- Contact-count and listing success bind `work_artifacts[]` with `kind=table` when Observation `structured.rows` exist. Count queries use one provider-total row (`system`, `object`, `count`, `source`) — not a sample of contacts from `limit: 1`.
- Follow-up `Show me that table` / `Open the report` uses `execution_path=listing_f2_read_resume`, reconstructs GET `/api/assistant/conversation/{id}/state` `execution_result`, `provider_reinvoked=false`. No second READ or WRITE.

On READ-only public browser sessions:

- `execution_path`: `computer_browser_read`
- `execution_strategy`: `browser_cdp` (Chromium session). `computer_use` remains approval-gated interact and is not this slice.
- Observation `structured.visits[]`: `{url,title,action,screenshot_digest,dom_excerpt}` from Playwright, not httpx.
- Resume `What was the second page URL?` / `Show me that report` → `computer_browser_read_resume`, `provider_reinvoked=false`.

On governed public-browser interact (HMAC confirm, Playwright once):

- `execution_path`: `computer_browser_interact_confirm` then `computer_browser_interact_resume`
- `work_artifacts[].kind`: `table`
- Observation `structured.rows[]` and `execution_result.structured.rows[]`: `{field,value}` from sealed submitted fields
- `execution_result.structured` also carries `plan_id`, `observation_ids`, `exportable`, `kind`, `execution_path`
- Resume (`Show me that table`, field questions) reconstructs GET `/api/assistant/conversation/{id}/state` `execution_result`. No second Playwright run.

Diagnostic plans may carry `ExecutionPlan.entity_id` and `task_state.business_entity` when an accepted join exists. Do not render that as a live multi-provider census.

## Presentation (Command OS + 3.0 Plus)

Consume `execution_result` / `work_artifacts[]` as the only artifact model. Do **not** invent UI-only artifact state.

- `ChatExecutionPanel` and `GravitreAIWorkCanvas` render `structured.rows` as the finished table (generic columns from row keys).
- Preserve kind, plan identity, Observation linkage, provenance, field/value structure, exportability, resume.
- LIVE_UI_PROVEN remains **pending** while owner-live frontend acceptance is blocked by authentication. Contract work is not a substitute for that proof.

Do not invent Enable toggles, prices, or Certified badges from these fields.
