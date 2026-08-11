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
4. **List populate honesty** (`list_populate_honesty.py`): for populate-intent workflows only
   (MSP list builder / enrich membership, NL populate language, or planned `lists.add` /
   `add_contact`), require membership proof (`added_count` / `contact_count` > 0 or per-contact
   vendor evidence) before COMPLETED. Empty shell → `partial_success` with reason
   `list created, 0 contacts added`.
5. **Create-only stays create-complete:** Prospecting Pack scout lists and chat
   `LIST_CREATE_INTENT` without populate language do **not** require add steps.
6. BusinessOutcome timeline renders clickable **Open completed work** from `evidenceUrl`.
7. Runs detail **Completed work** panel (all runs, not only chat) with **Open in source**.

## Out of scope (this PR)

AdWords / Google Analytics / Outlook — **not** audited end-to-end for population honesty.
Tracked as a separate follow-up (same rigor as Apollo/HubSpot). Do not expand “connectors
covered” summaries to include these three until that audit lands.

## Schema prerequisite (discovered in live proof 2026-08-02)

`workflow_runs_status_check` in prod did **not** include `partial_success`, so Module A
honesty terminals failed `run_persisted` while audit/notify still fired. Migration
`20260802223452_workflow_runs_partial_success_status.sql` adds the status. **Do not merge
claiming live PASS until that migration is applied and both Apollo directions re-run with
persisted statuses.**

## Verify

- Unit: `pytest backend/tests/services/test_connector_output_refs.py backend/tests/services/test_list_populate_honesty.py -q`
- Live (before merge): empty-shell Apollo populate-intent → `partial_success` + reason; populated
  Apollo → `COMPLETED`; one HubSpot “Open in source” URL resolves to a real list object.
