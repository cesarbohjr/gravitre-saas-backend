# Connector workflow step handlers

**Scope:** Map builder connector nodes → executable `invoke_tool` steps for all shipped vendors.

---

## Problem

The workflow builder stored vendor actions on `connector` canvas nodes (`tool_action: hubspot.contacts.search`), but `graph_to_definition()` only mapped Slack, email, and webhook to dedicated step types. Every other vendor action compiled to **`noop`**, so workflows never called `invoke_tool`.

---

## Fix (2026-06-16)

| Layer | Change |
|-------|--------|
| `backend/app/workflows/builder_sync.py` | Connector/tool nodes with vendor actions compile to `invoke_tool` + `config.action` |
| `definition_to_builder_nodes()` | Round-trip `invoke_tool` → `connector` node with `tool_action` |
| `context_packs.py` | Workflow/connector context resolves vendor from `invoke_tool` action prefix |

Execution path was already wired: `InvokeToolHandler` + `params_for_step("invoke_tool", …)` + `invoke_tool()`.

---

## Verification

```bash
cd backend && python -m pytest tests/workflows/test_builder_sync.py -q
```

Builder compile tests cover HubSpot search and Jira create round-trip.

---

## Usage in workflow definitions

```json
{
  "id": "hubspot_leads",
  "name": "Search leads",
  "type": "invoke_tool",
  "config": {
    "connector_id": "<uuid>",
    "action": "hubspot.contacts.search",
    "param_sources": {
      "filterGroups": "$hubspot_filter_groups"
    }
  }
}
```

See also: marketing (`analytics.reports.run`, `hubspot.contacts.search`) and devops (`jira.issues.create`) seeded workflows.
