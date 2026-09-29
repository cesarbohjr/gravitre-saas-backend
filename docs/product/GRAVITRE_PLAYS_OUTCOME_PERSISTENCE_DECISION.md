# Gravitre Plays / Outcomes — business-result persistence decision

Date: 2026-09-29

## Decision

Do **not** create a second generic outcome store.

The existing architecture already has three relevant layers:

1. `ExecutionOutcomeEvent` / `finalize_execution_outcome` — terminal execution truth.
2. `BusinessOutcome` — read-only customer-facing projection of workflow/run
   execution, verification, evidence and presentation.
3. `intelligence_outcome_events` — tenant-scoped learning/measurement event
   substrate with workflow/run/entity, confidence, before/after value,
   measured-at and metadata fields.

A Play business result is not the same thing as an execution outcome.
Therefore the Play program will persist **typed Play business-result events
inside the existing `intelligence_outcome_events` substrate**, using a
dedicated event type and contract. It will not overload
`ExecutionOutcomeEvent` and it will not create another workflow-result table.

## Why this is the smallest canonical extension

`intelligence_outcome_events` already has:

- `org_id`;
- `outcome_event`;
- `entity_type` / `entity_id`;
- `workflow_id` / `workflow_run_id`;
- `agent_id` / `connector_id`;
- `confidence_score`;
- `before_value` / `after_value`;
- `measured_at`;
- `measurement_status`;
- `metadata`;
- org-scoped RLS.

The remaining Play-specific fields can be carried in typed metadata without
creating a duplicate event backend:

- Play key/version/instance;
- metric key and outcome type;
- delta, unit, currency;
- attribution type/weight;
- source-system/source-record references;
- evidence ids;
- actions involved;
- verification state/method;
- occurred-at / recorded-at semantics.

## Verification states

The Play business-result contract uses:

- DETECTED
- RECOMMENDED
- ACTIONED
- PENDING VERIFICATION
- VERIFIED SUCCESS
- VERIFIED FAILURE
- INCONCLUSIVE

These are business-result states. They do not replace workflow run statuses.

A provider accepting a request can support ACTIONED. It cannot by itself
produce VERIFIED SUCCESS.

## Relationship to BusinessOutcome

`BusinessOutcome` remains the canonical customer-facing projection of an
execution/run.

A Play result may reference the same workflow/run and evidence, but the
business-result event answers a different question:

**Did the business metric/result actually change, with what evidence and
attribution?**

The existing BusinessOutcome DTO should not be expanded to claim revenue,
retention or marketing impact until a corresponding verified Play business
result exists.

## Metric observations

No general `MetricObservation` table is added yet.

For the initial Plays, baseline/result values can be stored on the typed Play
business-result event when a source-of-record measurement exists. If later
dashboard or historical comparison requirements need independent KPI
snapshots, a narrow MetricObservation contract can be added then.

## Phase result

OUTCOME_PERSISTENCE_DECISION = REUSE_INTELLIGENCE_OUTCOME_EVENTS

NO_SECOND_OUTCOME_STORE = TRUE

EXECUTION_SUCCESS_NE_BUSINESS_SUCCESS = ENFORCED
