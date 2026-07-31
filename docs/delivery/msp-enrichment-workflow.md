# MSP Prospects Clay Enrichment → HubSpot Sync

Delivery note for marketplace workflow `msp-prospects-clay-hubspot-enrichment` and Prospecting pack install bundle.

## Goal

Enrich an **existing** Apollo contact list (`MSP Prospects`) via Clay, sync enriched contacts to HubSpot CRM, and add them to an **existing** HubSpot **static list** (`MSPs`).

## Chat prompt (orchestration-friendly)

```
Use Clay to enrich the existing Apollo contact list "MSP Prospects", then add those enriched contacts to the existing HubSpot static list "MSPs".
```

Key wording:

- **existing** — avoids create-list shortcuts
- **HubSpot static list** — not “segment” (HubSpot lists API uses list IDs)
- Quote exact list names
- Name **Clay** explicitly
- Use **then** for step ordering

## Workflow steps

| # | Step ID | Type | Action / Agent |
|---|---------|------|----------------|
| 1 | `apollo_lists` | `invoke_tool` | `apollo.lists.list` |
| 2 | `prepare_clay_batch` | `agent` | Lead Enrichment Coordinator |
| 3 | `clay_push` | `invoke_tool` | `clay.leads.push` |
| 4 | `clay_outputs` | `invoke_tool` | `clay.workflows.output.get` |
| 5 | `hubspot_crm_sync` | `invoke_tool` | `clay.crm.sync` |
| 6 | `hubspot_list_membership` | `agent` | Lead Enrichment Coordinator |

Definition source: `backend/app/marketplace/workflows/msp_enrichment_workflow.py`

## Install variables

| Key | Required | Default | Notes |
|-----|----------|---------|-------|
| `APOLLO_LIST_NAME` | No | `MSP Prospects` | Apollo label to locate |
| `HUBSPOT_LIST_ID` | **Yes** | — | Numeric ID from HubSpot list URL |
| `HUBSPOT_LIST_NAME` | No | `MSPs` | Reference label for agent steps |

## Required connectors

- **Apollo** — list discovery (`apollo.lists.list`)
- **Clay** — BYO API key or webhook (`clay.leads.push`, `clay.workflows.output.get`, `clay.crm.sync`)
- **HubSpot** — CRM sync target + `hubspot.lists.add_contact` (agent step)

## Install paths

1. **Marketplace workflow template** — slug `msp-prospects-clay-hubspot-enrichment` in seed catalog
2. **Prospecting intelligence pack** — installs Lead Scouting Analyst workflow **and** enrichment workflow + Lead Enrichment Coordinator agent

## Run parameters (workflow execute)

Optional runtime parameters for tool steps:

- `$clay_records` — records batch for `clay.leads.push`
- `$enriched_records` — output from Clay for `clay.crm.sync`
- `$hubspot_connector_id` — active HubSpot connector UUID for CRM sync

## Verification status

| Layer | Status | Evidence |
|-------|--------|----------|
| Schema / catalog validation | PASS | `pytest tests/marketplace/test_msp_enrichment_workflow.py` |
| Prospecting pack install (unit) | PASS | `pytest tests/marketplace/test_prospecting_pack.py` |
| Prod workflow execute | **NOT RUN** | Requires merge → deploy → run with Apollo + Clay + HubSpot connected |

## Known limits

- No `hubspot.lists.list` action — list membership requires `HUBSPOT_LIST_ID` at install
- `apollo.lists.list` lists labels only; agent step prepares contact export from list context
- Bulk `hubspot.lists.add_contact` runs inside agent step (one invoke_tool step = one contact)
