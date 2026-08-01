# False COMPLETED on idempotent / empty vendor writes

## User report (2026-07-31)

- Run `bd420e75-77e8-474c-aff9-57c7c23b64f6` — UI **COMPLETED**, 0 records, **0/0 steps**
- Timeline: `Found existing contact list "MSP Prospects" (id: 6a4d6a98461b000010c5ae7b).`
- Tags: `created_record` · `module_a_verified_output` · `presented`
- Apollo list empty (0 records); HubSpot had only smoke-test contacts
- Intent included Clay enrich + HubSpot static list — never executed

## Root cause (class-level)

1. **Idempotent Apollo `lists.create`** returns `already_existed=True` with `success=True`; Module A treated non-empty summary as verified create → **COMPLETED** + `created_record`.
2. **Chat connector finalize** created a run **without** `workflow_steps` → Runs UI **0/0** / “No steps recorded.”
3. **`LIST_CREATE_INTENT` routing** suppressed orchestration when the message also asked for Clay enrich + HubSpot sync → collapsed to single Apollo list create.

## Fix

| Layer | Change |
|-------|--------|
| Outcome | Idempotent find → run status `partial_success`, kind `found_existing_record`, verification `module_a_idempotent_find` |
| Summary | Explicit: no contacts added, no HubSpot sync |
| Steps | Persist `workflow_steps` row for chat-connector runs |
| Routing | Multi-system enrich/sync (Apollo+Clay+HubSpot) does **not** prefer single list-create |
| UI | `partial_success` badge (warning) on Runs |

## Verification

- Unit: `pytest tests/services/test_connector_outcome_effects.py tests/services/test_chat_connector_execution.py -q`
- Live: re-run MSP enrich prompt after Clay connected; expect orchestration plan (not lone `apollo.lists.create`) and **no** COMPLETED for empty shell find

## Apollo membership gap (class-level follow-up)

`apollo.lists.create` / `apollo.lists.list` alone never moved contacts into MSP Prospects. Closed in code by:

| Tool | Vendor route | Role |
|------|--------------|------|
| `apollo.contacts.search` | POST `/api/v1/contacts/search` (+ optional `contact_label_ids`) | Read list membership / emptiness |
| `apollo.lists.add` | POST `/api/v1/labels/add_entity_ids_to_label_names` | Write contacts onto list names |

MSP enrichment workflow steps now: `lists.list` → `contacts.search` → agent (prospect + `lists.add` if empty, else Clay batch) → Clay → HubSpot list membership.

## Status

- Outcome / routing / steps persistence: shipped earlier (honesty fix `7b56a80b`).
- Apollo membership tools + workflow rewrite: merged as `46b1cec3` (PR #182).
- **Prod tip:** `559427e1` (includes honesty fix `7b56a80b` + Apollo populate `46b1cec3`).
- Live full populate (contacts onto MSP Prospects + Clay enrich + HubSpot): **NOT RUN** — still needs Clay connector on smoke org + fresh chat/workflow run.
