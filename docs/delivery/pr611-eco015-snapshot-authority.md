# ECO-015: discovery snapshots and fresh action readiness

Base: PR #611 at `323a9dbd1ed569e2508c7458d611082ed2541937`.
This batch preserves the preceding vendor-ownership repair and all finding-level
acceptance criteria. It does not certify the whole finding.

## Caller inventory and scope

| Source chain | Observed source behavior |
| --- | --- |
| ReAct `_react_loop`, `_execute_tool_call` -> ToolRegistry `list_connected_integrations` -> snapshot wrapper | Fresh vendor-level requests, default force_live true. Actual wrapper chain exercised here; full ReAct suites retained. |
| ToolRegistry capability execution -> `list_connected_integrations` | Fresh vendor discovery used to resolve a capability. No concrete action key passed at this site. |
| ChatConnectorExecutionService `process_turn` -> `_live_connected_integrations` -> ToolRegistry -> snapshot | Helper forwards an optional action key, but its actual application caller omits it. |
| Chat `_verify_plan_executable` / explicit HubSpot contact-search readiness | Supplies actual action keys directly to canonical availability lookup, bypassing the snapshot wrapper. Previous batch verified the actual plan preflight. |
| Assistant knowledge retrieval -> snapshot wrapper | Explicit force_live false; vendor discovery only. |
| Pipecat keyterm bootstrap -> snapshot wrapper | Explicit force_live false; vendor discovery only. Voice implementation and audio acceptance remain PR #610 owned. |
| Snapshot prefetch -> snapshot wrapper | Fresh vendor discovery; best-effort background use. |
| Memory source-liveness invalidation -> `invalidate_org_connected` | Clears an organization's snapshots; existing invalidation tests retained. |

An AST named-call scan of backend/app found no concrete action-key producer
calling the cached wrapper beyond forwarding parameters in the chat helper and
ToolRegistry wrapper. This is a bounded static inventory, not proof that every
dynamic caller is absent or that any caller is deployed/active. The action-key
reproduction below is therefore API-contract evidence, not production traffic.
The fresh vendor-level request path does have concrete source callers.

## Four failures reproduced before source repair

The real ToolRegistry wrapper, snapshot wrapper and canonical availability
evaluator ran with synthetic connector/OAuth storage and auth-health I/O:

1. A cached generic `[hubspot, slack]` snapshot answered a HubSpot contacts-write
   readiness query even though stored grants had only contacts-read permission.
2. A scoped HubSpot read overwrote the broad discovery snapshot, hiding Slack
   from the following generic cached lookup.
3. An explicit PermissionError from the connector repository was swallowed;
   a forced refresh returned the old positive snapshot instead of propagating
   the tenant denial.
4. A repository outage during a forced refresh also returned old positive
   readiness.

All four new regressions failed against the unmodified base. These failures
establish cache/readiness semantics, not a bypass of final provider credentials,
actor authorization, write approval or dispatch gates. No provider was invoked.

## Bounded repair

The existing cache now stores **vendor discovery only**. A supplied action key
always runs the existing availability evaluator, and its filtered result neither
reads nor replaces the generic snapshot. The requested force_live value still
controls remote health validation; force_live false does not become a live
provider probe. No per-action cache, new executor or authorization authority is
introduced.

An explicit PermissionError invalidates that organization's discovery snapshots
and propagates. Other refresh errors return an empty list rather than a cached
positive. A valid non-forced discovery cache hit remains available without a
refresh; it is a discovery snapshot, not proof of current action authority.
Existing cache signatures, TTLs and tenant/environment partitioning remain.

## Local evidence

**162 tests passed** with normal backend conftest:

```text
tests/services/test_connector_snapshot_authority.py
tests/services/test_agent_platform_optimizer.py
tests/services/test_memory_source_liveness.py
tests/connectors/test_eco015_action_vendor_authority.py
tests/connectors/test_connector_availability_service.py
tests/services/test_chat_connector_execution.py
tests/services/test_connector_execution_matrix.py
tests/operators/test_react_engine.py
```

Eight new snapshot tests cover the four failing cases plus discovery cache hits
and copy isolation, successful forced refresh, stored-scope revocation rechecks,
TTL/environment/tenant boundaries and org-scoped invalidation. The preceding
783 registered catalog ownership pairs remain covered. No assertions, security
checks or OAuth scope requirements were weakened. The task Python lacks socksio;
proxy variables were unset for these isolated tests.

## Exact-head CI prerequisite

All ten workflows passed on the base SHA, including
[Core45102959562](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45102959562),
[Operations45102959538](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45102959538),
and [QA1245102959527](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45102959527).
All five required Core checks succeeded. Backend log: **17,486 passed, 64 skipped,
14 subtests passed**, 59m18s. The full pytest step completed before the final
offline Core checks; those checks also completed successfully.

QA12 runtime job137457819435 passed its mandatory PostgREST16.6 gate with
PostgreSQL18.7: **20 passed, zero skips**. Independently downloaded/parsed
[artifact14786676785](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45102959527/artifacts/14786676785)
matches base git_sha/status PASS/tests20/skipped0, external_project_used false
and certifies_whole_finding false. ZIP SHA256:
`b3e704b4b0596589acba217c52a1740ad2cbc1c4f0839f92050d9d6ff1acc344`.
Existing completed artifact and signed QA evidence were preserved, not repeated.

Fresh hosted CI on the published repair SHA remains required. Skipped live,
provider and billing jobs and the physical-voice placeholder are not acceptance.
Deployed caller traffic, all-provider scope completeness, native/managed
precedence, independent durable/provider receipts and rollback/owner criteria
remain open. No merge, deployment, live dispatch, provider write, migration or
retirement is performed. Both audit stores and twelve workflows remain.
**0/43 findings certified closed**.
