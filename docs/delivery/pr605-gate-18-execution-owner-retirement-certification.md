# PR #605 — Gate 18: execution-owner callsite evidence and per-candidate retirement decisions

Date: 2026-11-05. **Status: source-callsite implementation committed; production execution graph NOT certified; retire approvals = zero.** This is not authorization for merge, deployment, data changes or legacy deletion.

## 1. Existing test failure and correction

Independent cross-surface CI [42108686850](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42108686850) failed: `test_python_legacy_import_and_dynamic_dispatch_candidates` (2 passed / 1 failed). The exporter did not recognize `from importlib import import_module; import_module(...)` as an importlib dynamic candidate. The AST visitor now recognizes imported aliases and emits the test's `dynamic_python_dispatch_candidate` classification. **Re-run required**; a source fix is not a certified passing test.

## 2. Source-level ownership graph: executable inventory, bounded claims

Committed `backend/scripts/pr605_execution_owner_edges.py` with focused tests `backend/tests/scripts/test_pr605_execution_owner_edges.py` and incorporated both in `.github/workflows/pr605-cross-surface-ownership.yml`. The script parses actual Python AST call expressions rather than merely imports, resolves local import aliases to module-qualified targets when possible, records source files/line numbers, and flags registration/callback and unresolved dynamic-dispatch candidates. It reads twelve targeted **existing** source files and makes no application imports, provider requests, SQL calls or production writes.

| Owner candidate | Inspected source | Boundary / decision |
|---|---|---|
| Assistant ingress | `backend/app/routers/assistant.py` | Calls/source owner; dispatch branches still require runtime traces |
| Voice WebSocket ingress | `backend/app/routers/pipecat_voice.py` | WS owner; connection/session/PCM traffic still untraced |
| Agent decision | `backend/app/operators/agent_intelligence.py` | Possible decision owner; complete caller and outcome chain not proven |
| Autonomous agent loop | `backend/app/services/autonomous_execution_loop.py` | Policy decision module; module explicitly states it does not execute tools |
| Workflow adapter | `backend/app/services/workflow_execution_strategy.py` | ExecutionPlan/Observation strategy semantics present; workflow invocation not necessarily observed |
| Connector execution | `backend/app/services/chat_connector_execution_service.py` | Catalog, approval and tool access dependencies; tenant-authorized successful invocation still unverified |
| Connector readiness | `backend/app/connectors/connector_availability_service.py` | Declared canonical availability/readiness; individual connected provider/scope unverified |
| Connector catalog | `backend/app/services/connector_execution_matrix.py` | Static tool catalog distinct from tenant-ready execution |
| Execution outcome | `backend/app/services/execution_outcome.py` | Source documents sole terminal authority + deliberate repository projection; all caller/side-effect parity not proven |
| Durable domain-event relay | `backend/app/services/domain_events.py` | Postgres outbox/lease/retry semantics declared; actual handler side effects require proof |
| Relay scheduler | `backend/app/schedulers/domain_event_relay_scheduler.py` | Env-gated periodic relay and sample operational logs; active consumer registrations/side effects not exhaustive |
| Temporal worker registry | `backend/app/temporal/worker.py` | Explicit workflow/activity registration, task queue `gravitre-main`; production worker presence and activity not attested |

**Limit:** AST call sites are *potential* calls, not proven runtime executions. Python injected objects, method dispatch through locals, dynamically selected providers, tool registry, RPC/SQL and TypeScript component call sites need additional tracing. Source calls must never be described as observed production invocations.

The earlier cross-surface file inventory still exists and is independently tested; it covers browser Pipecat WS and Next.js voice session proxy literal paths. Both reports deliberately emit `retirement_certified=false` and a nonzero list of unknowns. CI will check commit identity and retain both JSON artifacts. At the time of writing these latest scripts/tests have not been independently certified green.

## 3. New read-only production observation (bounded HTTP sample)

Railway project `spirited-communication`, production backend service `gravitre-saas-backend`, deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb`. A read-only `get_logs(types=[http],limit=100)` retrieval returned **101 records** ranging 2026-11-05 15:04:13 to 19:09:10 UTC. Distribution: 96 HTTP 200, three 401, one 403, one 404. Observed endpoint occurrences include `GET /api/approvals` 11, `GET /api/agent-jobs` 4, `POST /api/webhooks/hubspot/inbound` 3, `GET /api/metrics/overview` 10, `GET /api/organizations` 9. Counts are **sample-specific**, with user-agents including Node/headless browser; do not equate requests with successful end-user task completion. HTTP proxy logs show ingress/response, not internal method call stacks, WebSockets or business outcome verification.

Railway distributed-trace query for the production backend, window 2026-11-05 20:16:14–21:16:14 UTC returned **zero trace records**. This is a *telemetry coverage gap*, not proof that no work executed. No deployment, tracing configuration, credentials or customer data were changed.

## 4. Individual retirement candidate certification decisions

| Candidate | Current action | Evidence reason | Retirement decision |
|---|---|---|---|
| Classical ReAct / LIVE phrase safety-net | CONSOLIDATE CANDIDATE | Source still performs tool SSE/governed defer | **BLOCKED** — need authorized tool-read/write equivalence, active caller flags, text/voice parity, SSE and rollback |
| Legacy voice HTTP/Talk, PCM BufferSource renderer | CONSOLIDATE CANDIDATE | Browser has WS + HTTP session and dual renderers | **BLOCKED** — need real session/client compatibility, fallback frequencies, STT/TTS/PCM regression |
| Alternate context/memory/prompt builders | AUDIT/CONSOLIDATE CANDIDATE | Multiple entry points in source | **BLOCKED** — need actual read/write authority, tenant/provenance, model and context outcomes |
| Duplicate workflow/run projection stores | KEEP while migrating | Approval FK, status differences and intentionally mirrored outcomes | **BLOCKED** — lossless v2 semantics, consumers, migration, rollback and per-row approvals |
| Domain event relay and outbox | KEEP | Source-backed durable delivery; previous delivery counters sampled | **NO RETIREMENT** — critical outcome consumers and replay semantics need preservation |
| Connector readiness, catalogs, approval/writes | KEEP + VERIFY | Distinct static vs runtime tenant availability | **NO RETIREMENT** — must preserve consent/scope and unauthorized-write fence |
| Temporal worker/asyncio scheduler split | AUDIT | Worker env-gated; hosted worker/queue not proven | **BLOCKED** — identify configured worker, backlog, schedule owners, crash recovery |
| Separate Railway frontend project | RETIRE CANDIDATE | Previous metadata: failed deployment and no assigned domains | **BLOCKED** — verify external consumers, scheduled work, spend, safe rollback |
| Legacy Redis/service caches | KEEP pending proof | Production Redis service active; consumers/recovery not exhaustively mapped | **BLOCKED** — key namespaces, leases, eviction and runtime semantics |

**Certification count: zero candidates approved for deletion.** Keeping required contracts is a positive preservation decision, not confirmation the component is defect-free or optimal.

## 5. Required next remediation

1. **Repair and rerun independent ownership workflow.** Inspect its test log, SHA and both exported JSON files. Fix any source parsing failures. Do not count skipped/deselected tests as passes.
2. **Runtime correlation with privacy-safe tracing:** instrumentation design must link request/turn ID to authenticated surface, selected mode/decision owner, tool capability and authorization, queued agent/play/workflow run ID, provider observation, outbox event and final result. Avoid payloads, API keys, tokens, transcripts and PII in metadata. Review telemetry sampling/retention/consent before production enablement.
3. **Map dynamic execution:** add explicit dispatch/registration edges for agent/play/workflow registries; test connected/disconnected/scoped read, approved write, revocation, crash/restart, event handler replay and terminal-state truth on ephemeral data.
4. **Production service topology:** attest Temporal worker and actual live flag/queue consumers, Vercel→Railway origin and Supabase project ref through authorized redacted checks. No inferred environment binding.
5. **Certify individually:** approve retirement only for a candidate with zero unknown protected callers, verified consumer migration, same-contract replacement, required security/functional regression tests, rollout/rollback and named reviewer sign-off. Keep all other candidates non-retirable.

## 6. Release truth

Gate 18 remains **OPEN** until source extractor tests and artifacts are certified, then privacy-safe runtime spans / active consumer traces close the execution-ownership holes. Full CI must pass against final PR head, not prior green commits; production DB identity is independent. PR stays draft/unmerged/undeployed; no schema or historical reconciliation authorized.
