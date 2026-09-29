# Gravitre Plays — canonical workflow binding decision

Date: 2026-09-29

## Decision

A Play does not own executable workflow steps.

Tenant Play-to-workflow bindings are stored as metadata on the existing
`workflow_defs.config` object under the `play` key.

Example:

```json
{
  "play": {
    "key": "revenue-recovery",
    "version": "1",
    "bound_at": "...",
    "bound_by": "...",
    "execution_authority": "canonical_workflow_runtime"
  }
}
```

The canonical workflow remains executable through the existing workflow
runtime, versions, nodes, edges, approval gates and run records.

## Why this avoids a second workflow model

The binding contains no steps, nodes, connector execution instructions,
schedules, approval policy or runtime state.

It only answers:

**Which canonical workflow is currently being used to operationalize this
outcome-oriented Play?**

## API

Read:

- `GET /api/plays/{play_key}/workflow-bindings`

Admin-only bind:

- `POST /api/plays/{play_key}/workflow-bindings`

Admin-only unbind:

- `DELETE /api/plays/{play_key}/workflow-bindings/{workflow_id}`

Binding and unbinding are audited.

## Dashboard

The existing Dashboard displays the number of canonical workflows bound to each
Play. No separate Play workflow builder is introduced.

## Execution rule

Binding a workflow does not execute it.

All execution remains subject to the canonical workflow runtime and canonical
approval/governance paths.

## Result

PLAY_WORKFLOW_BINDING = EXISTING_WORKFLOW_METADATA

SECOND_WORKFLOW_RUNTIME = NO

BINDING_CAUSES_EXECUTION = NO
