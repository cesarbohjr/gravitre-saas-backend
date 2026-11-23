# DEC-009: latency bridge source contract

Base: `65af0f49e793fdcd10e7efe14c81b9b6e5804774`. This batch adds regression
evidence without changing production code, telemetry fields, feature flags or
privacy policy. DEC-009 remains open. Local isolated I/O is not durable acceptance.

## Exact-head prerequisite

All ten PR workflows succeeded on the base, attempt 1. Core
[45110752057](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45110752057)
completed all five required contexts; backend job `137482374809` reported
17,494 passed, 64 skipped and 14 passing subtests. Operations
[45110752064](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45110752064)
also succeeded. The retained QA12
[artifact 14789219228](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45110752054/artifacts/14789219228)
was already independently downloaded and parsed: exact base SHA, PASS, 20 tests,
zero skips, PostgREST 16.6 / PostgreSQL 18.7, no external project, whole-finding
certification false. ZIP SHA256:
`2238aa1e21d36d41b21632e021e4bd6e7630176d94ef3163673554172d9093a9`.
It was not downloaded again in this batch.

## Source ownership and callers

- `AgentIntelligence.execute_task_streaming` invokes `apply_unified_turn_live`
  and the separate `schedule_unified_turn_shadow` entrypoint. The scheduler
  avoids a duplicate shadow run when LIVE is enabled and otherwise checks the
  shadow flag. Both routes reach `run_unified_turn_shadow`.
- That runner calls `_log_unified_turn_breakdown` on success, model-call error
  and missing completion. All three application call sites explicitly pass
  `message_id=None`; only the success call supplies the model. This is a static
  source trace, not a production usage or feature-flag observation.
- `_log_unified_turn_breakdown` invokes the existing
  `bridge_unified_turn_breakdown_to_pipeline`. The bridge maps eight known stage
  keys plus wall TTFT and calls `log_pipeline_latency` asynchronously, with a
  synchronous fallback when no loop is running.
- `log_pipeline_latency` owns the `ai_pipeline_latency` insert and schedules a
  ClickHouse `gravitre.pipeline_events` replica only after that insert succeeds.
  The existing speculative scope defers latency writes until adoption and drops
  discarded writes. The test executes these real source functions with database
  and ClickHouse I/O replaced by local recording doubles.
- The admin-only, org-context `/performance` route calls
  `load_performance_dashboard`; its existing Postgres fallback and ClickHouse
  query filter by organization. `_build_pipeline_waterfall` consumes the same
  bridge stage names. The new test reaches that actual waterfall builder, not
  the authenticated HTTP route or a running analytics/database server.
- Model-call metering is separate: the runner invokes `record_tool_model_call`
  for completed model rounds. The bridge does not itself persist provider,
  token usage or estimated cost. This batch neither duplicates metering nor
  claims an end-to-end provider/cost reconciliation.

## Executed coverage and no-change decision

`backend/tests/services/test_dec009_pipeline_bridge_contract.py` contains 14
passing cases, with the normal backend conftest loaded:

- Actual producer -> bridge -> writer payloads -> actual waterfall builder:
  nine stages, exact durations, org/message/model propagation, classical-series
  separation and analytics replica payload identity.
- Only declared latency fields enter those recording sinks; arbitrary breakdown
  fields do not become persistence columns. This does not certify log redaction
  or authorize new correlation fields.
- Seven malformed/nonfinite/negative stage inputs do not erase a later valid
  model-total or wall stage. Empty organization/breakdown emits nothing; zero
  duration remains valid on the synchronous path.
- An injected first-stage writer failure does not abort the later stage.
- Real speculative scope: no writer or replica call before adoption, discarded
  scope produces zero calls, adopted scope emits once.

The first test draft had three harness errors (wrong waterfall key and missing
required scope argument); those were corrected to the existing APIs. They were
not production failures. No implementation regression was reproduced within
these cases, so no production repair is justified by this batch.

Combined with existing performance-cache, unified reasoning and context-size
tests: **75 passed, one skipped**. The skip is the existing optional uncached
tiktoken encoding check (`#366`), not a bridge test. All 14 new cases ran.
Command, from `backend`, using the task's prepared Python/dependency environment:

```sh
python -m pytest -q -rs \
  tests/services/test_dec009_pipeline_bridge_contract.py \
  tests/test_performance_caching.py \
  tests/services/test_unified_turn_reasoning.py \
  tests/services/test_unified_turn_context_size_breakdown.py
```

Proxy variables were unset for isolated execution because the task Python lacks
`socksio`. No provider, remote database or live endpoint was invoked.

## Remaining acceptance

New exact-head hosted CI is required after publication. No change to release or
closure flags is made. These tests do not prove actual LIVE/classical caller
coverage, end-to-end spans, per-turn correlation (current caller IDs are null),
provider/billing cost accuracy, deployed dashboard or tenant/RLS behavior,
analytics durability, production privacy approval or rollback. Existing signed
QA preflight `44863581946` and cleanup evidence remain preserved and unrepeated.
There are still **0 of 43 findings certified closed**.
