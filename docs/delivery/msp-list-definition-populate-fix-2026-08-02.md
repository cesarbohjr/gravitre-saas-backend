# MSP / list workflow definition fix — create without populate

Date: 2026-08-02  
Depends on: PR #184 honesty layer (reporting) + this definition change (actual finish)

## Problem

Honesty alone tells operators the run did not populate. Definitions still needed to
**actually finish** membership via deterministic `invoke_tool`, not agent instructions.

## Prod audit (smoke org + probe org)

| Workflow | Create shell? | Deterministic add? | Verdict |
|----------|---------------|--------------------|---------|
| MSP Prospects Clay Enrichment → HubSpot Sync | No (assumes list) | Was agent-only `lists.add` / `add_contact` in task text | **P0 fix** |
| Prospecting Apollo Lead Scout | Yes (`lists.create`) | No — create-only by design | Leave create-only |
| Canvas / Module D probes | Yes (test harness) | N/A | Out of scope |
| MSP Prospecting & List Builder | Not installed under that name on smoke org (legacy “MSP NVD CVE Lookup” still present) | Builder had agent-only populate | **P0 fix in builder** |

## Code fixes (builders)

1. **`msp_prospecting_list_workflow.py`** — after `apollo.lists.create`, add
   `apollo.lists.add` (`entity_ids` from `apollo_people_search`); after
   `hubspot.lists.create`, add `hubspot.contacts.create` + `hubspot.lists.add_contact`.
   Agents qualify/summarize only.
2. **`msp_enrichment_workflow.py`** — add `apollo.people.search` + `apollo.lists.add`
   and `hubspot.lists.add_contact` as tools; agents prepare Clay / summarize only.
3. Stamp `entity_ids` / `primary_contact_id` / `hubspot_contact_properties` on Apollo
   people/contacts search; stamp HubSpot `contact_id` on contacts.create and Clay CRM sync.
4. Merge `params` + `param_sources` in `params_for_step` so literals + from_step coexist.

## Create-only (intentional — do not force populate)

- Prospecting Pack scout (`build_prospecting_workflow_steps`) — close task defers
  “next membership steps”. Honesty docs keep this COMPLETE when create is proven.

## Out of scope (separate)

- AdWords / GA / Outlook — STA-337
- Reinstalling pack definitions onto existing org `workflow_defs` (builders alone do not
  rewrite installed graphs). Needs pack reinstall or one-shot upsert after deploy.

## Verify

- `pytest backend/tests/marketplace/test_msp_prospecting_list_workflow.py backend/tests/marketplace/test_msp_enrichment_workflow.py backend/tests/marketplace/test_workflow_contract.py -q`
- After deploy + pack reinstall: live MSP run shows `apollo.lists.add` / `hubspot.lists.add_contact`
  step rows with `added_count` > 0 and COMPLETED (not empty-shell partial).
