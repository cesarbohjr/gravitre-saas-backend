# LIVE to classical: preserve all queued read choices

Base: `6390893a04da64bc5b7fb0f74f4aec7dd4b6c66f` (PR #611).
All ten hosted PR workflows passed on that base, including Core
[45077849389](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45077849389).
Base CI is not verification of this new repair.

## Confirmed bounded defect

Source chain: `capability_evidence_plan.apply_evidence_plan_handoffs` ->
`live_classical_handoff.stash_handoff_queue` -> agent intelligence's
`arm_from_task_state` -> `ReActEngine._react_loop` -> `_execute_tool_call`.
This is source tracing and local execution, not deployed caller traffic.

The actual ReAct loop pinned only `peek_handoff()` (the first choice) after
tool narrowing. The allowed-name set was then fixed for the entire loop.
The second queued read could be available in the registry but absent from that
set. ReAct rejected it as `tool_not_available` and stopped for human input.

Before changing source, both streaming and non-streaming regression cases failed:
the second read `hubspot_get_contact` was rejected, although the isolated registry
returned it alongside `hubspot_search_contacts`. Normal backend conftest loaded.

## Repair and negative coverage

`pending_handoff_tool_names()` snapshots all remaining queued tool names and
invoke-action aliases without consuming them. The loop pins those names only
from the existing available registry output, using the existing pinning helper.
No registry admission, write approval, authorization or dispatch gate is bypassed.
No new executor or model selection is introduced.

Four actual-loop cases cover streaming/non-streaming with and without a third
unavailable queued name. Both available reads execute once in order. An unavailable
third choice still stops for human input with zero registry calls for that name.
Queued reads require no model selection; only final synthesis calls the isolated
model. A separate snapshot test checks aliases, deduplication, non-consumption,
queue advancement, exhaustion and replacement across turns.

Local checks:

```text
python -m pytest tests/operators/test_react_engine.py \
  tests/services/test_unified_turn_classical_fallback.py \
  tests/services/test_unified_turn_fallthrough_enum.py -q
78 passed

python -m pytest tests/services/test_react_write_gate.py \
  tests/services/test_react_write_gate_catalog_authority.py \
  tests/master_qa/test_master_qa_remediation_guard.py \
  tests/master_qa/test_runtime_guard_integration.py -q
35 passed
```

The task Python environment has a SOCKS proxy without socksio; proxy variables
were unset for these isolated tests. Model, registry/provider execution and audit
I/O are doubles in the new loop tests. They do not prove provider, persistence,
deployed SSE delivery or end-user acceptance. Assertions on call order and blocked
availability execute the actual loop and availability check.

## Finding relationship and remaining gates

DEC-002 and DEC-018 receive bounded tool-loop/handoff parity evidence. ECO-011
and DEC-001 share this prerequisite evidence; their wording-sensitive routing
and deployed latency requirements are not resolved by this change. Existing
explicit-boolean routing and connector-proposal tests remain intact. No phrase
fallback, audit store, legacy executor or workflow is retired.

Fresh exact-head full hosted CI is required after publication. Live caller traces,
SSE/approval parity, independent provider/persistence effects, rollback and owner
acceptance remain pending. All closure flags remain false: **0/43 certified closed**.

## Preserved DEC-008 hosted result

On the base SHA, QA12 run
[45077849419](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45077849419)
passed the mandatory real PostgREST16.6 gate: 20 tests, zero skips. The actual ZIP
[artifact 14776675351](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45077849419/artifacts/14776675351)
was independently downloaded and parsed. Its JSON matches the base SHA,
status PASS, tests20/skipped0, external_project_used false and
certifies_whole_finding false. Hosted PostgreSQL was 18.7.
ZIP SHA256: `18263f8f6acfc71556b6089f450ffd6adf44d455a72669b6656bc32d77bb4c30`.
This evidence is retained; deployed store parity remains unproven.
