# STA-337 remediation shipped (code) — 2026-08-03

**live_pass_claimed:** `false` (no Ads/GA/M365 live audit_events in this pass)  
**Code remediation:** complete for backlog items 1–6

## Changes

| Item | Change |
|------|--------|
| Outlook alias | `REGISTRY_ACTION_ALIASES`: send/list/batch → `microsoft365.*` |
| Outlook kill | Removed unmapped catalog actions (reply/rules/categories/get/folders) |
| Honesty gate | `microsoft365` added to `HONESTY_GATED_CONNECTORS` |
| Ads mutating | `.pause` / `.resume` in `MUTATING_ACTION_MARKERS` |
| Ads dual-name | `googleads.*` listed alongside `google_ads.*` in verified batch 09 |
| GA funnels | Demoted: removed catalog + priority executor; stub raises 501 |
| M365 send proof | Empty Graph 202 stamped `accepted_async` + `result_url` |

## Tests

`pytest` STA-337/Part5 related suite: **456 passed** (install_ready, aliases, outcome_effects, action_selection_gate, workflow_schemas_batch_50, output_schema_batches, action_catalog).

## Still required for honesty PASS

Live tip proof with `audit_events` for:
- `googleads.campaigns.pause|resume`
- `analytics.reports.run` (or `google_analytics.reports.run`)
- `microsoft365.mail.send` (or aliased `outlook.messages.send`)
