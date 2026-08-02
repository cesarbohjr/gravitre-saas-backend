# Completed work visibility (runs → connectors)

## User report

Production workflow/chat runs showed **COMPLETED** but Apollo had no curated populated list, HubSpot had no researched-contacts list, and the Runs UI did not make it clear **what landed where** — only that steps finished.

## Audit verdict

| Path | Actually writes? | Visibility of completed work |
|------|------------------|------------------------------|
| Chat connector (`execute_plan`) | Yes, via `invoke_tool` + outcome-effect honesty | Partial — run created, step often lacked `external_url` |
| Chat orchestration | Yes, multi-step | Better step summaries; vendor links inconsistent |
| Canvas / workflow `invoke_tool` | Yes | Run finalized to `/runs/{id}` only — no aggregated vendor URLs |
| Agent steps in MSP packs | Instructional; may skip `apollo.lists.add` / `hubspot.lists.add_contact` | Empty list **shells** can still “succeed” |
| Outlook catalog | Microsoft 365 Graph path is real; bare `outlook.*` catalog risk | Same link gap |

**Class gap:** `apollo.lists.create` / `hubspot.lists.create` ≠ list population. Membership needs `apollo.lists.add` / `hubspot.lists.add_contact`. Chat already downgrades idempotent finds to `partial_success`; workflow graph finalization did not aggregate per-step effects or deep links.

## Fix (existing structure — Runs + BusinessOutcome)

1. Stamp connector deep links + `outcome_effect` on chat + `invoke_tool` step `output_snapshot`.
2. Aggregate step refs into Module A `VerifiedOutputRef.external_url` + `metadata.connector_output_refs`.
3. Downgrade workflow COMPLETED → `partial_success` when every mutating step is unproven / already_existed / noop / async.
4. BusinessOutcome timeline renders clickable **Open completed work** from `evidenceUrl`.
5. Runs detail **Completed work** panel (all runs, not only chat) with **Open in source**.

## Verify

- Unit: `pytest backend/tests/services/test_connector_output_refs.py -q`
- After deploy: open a run → Completed work shows Apollo/HubSpot links when tools returned URLs; empty-shell finds show partial success honesty, not green create.
