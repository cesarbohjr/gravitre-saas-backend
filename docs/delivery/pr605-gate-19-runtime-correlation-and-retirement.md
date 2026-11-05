# PR #605 — Gate 19: inventory certification and privacy-safe runtime correlation

Date: 2026-11-05. Status: **bounded inventory certified at prior head; runtime instrumentation staged, not production enabled; retirement still blocked**.

## Exact earlier-head inventory certification

[PR605 cross-surface ownership workflow 42111333265](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42111333265) completed **SUCCESS** against `8c3f5c39f23cf94f53e18896183fea0cdbb88fbf`. Job `127539365483` reports `6 passed, 1 warning`; ten original source-owner candidates, twelve source-call owners, 1,001 AST method call edges, zero missing sources, and preserved `retirement_certified=false` assertion. Retained both JSON reports in [artifact 13453657302](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42111333265/artifacts/13453657302), ZIP SHA256 `55292fde60777a94239ca3c9fca1bb16faa0e0e62b97cc76d702f4c421d3c887`. The single warning was an unknown pytest `asyncio_mode` config option with minimal pytest install; it was **not** a skipped test.

**Scope certified:** source AST inventory and provenance assertions only, not actual production call execution. New commits must rerun applicable checks on their own head.

## Gate 19 engineering change

- `backend/app/services/runtime_execution_edge_telemetry.py`: opt-in `emit_handoff()` for owners `agent/play/workflow/connector/event_consumer/outcome/voice` and fixed stages. Disabled by default. Requires both explicit `PR605_EXECUTION_EDGE_TELEMETRY_ENABLED=true` and independent minimum-length `PR605_EXECUTION_EDGE_HMAC_KEY`. Produces short HMAC-SHA256 pseudonyms from caller-supplied opaque correlation ids, rather than emitting raw ids. Emits only fixed owner, stage, source code and digest; rejects arbitrary source strings containing spaces, punctuation or non-ASCII to prevent free-text payload logging.
- `backend/app/services/domain_events.py`: `DomainEventRelay._dispatch` marks per-event attempted, completed and failed handler phases using a fixed mapping for `execution.outcome_finalized` and `source.disconnected` or `other_event`. **Does not emit handler names, event body or user data.** HMAC correlation uses event primary key and remains disabled until separately enabled.
- `backend/app/services/workflow_execution_strategy.py`: emits fixed `workflow/observed/workflow_result` at the parent workflow-result observation boundary, HMACing plan id. It does not assume a workflow success just because a plan step produced an observation.
- `backend/tests/services/test_runtime_execution_edge_telemetry.py`: five focused tests for disabled default, missing key, no sensitive logging, whitelisting and stable cross-owner pseudonymous correlation using the same input id.
- `.github/workflows/pr605-runtime-edge-contract.yml`: independently executes the five privacy tests and Python compilation with no provider calls, no production keys or database access.

**Limits and operational safety:** the event PK and plan ID are not automatically the same identifier, so their traces are not an end-to-end linked business execution unless the producer explicitly propagates a *shared* correlation ID through an approved typed contract. Do not synthesize such linkage from timestamp proximity or matching request counts. Flag must remain **OFF** in all deployed environments until design review has approved privacy, retention, access controls, sampling, key rotation, logger sinks, security impacts, operator documentation and rollout/rollback. This change does not enable tracing in Railway/Vercel, alter production config, emit provider secrets or call live providers. Passing tests do not certify production observation.

## Candidate-by-candidate retirement decision after Gate 19

| Candidate | Current preservation / target | Runtime linkage status | Decision |
|---|---|---|---|
| Classical ReAct / LIVE fallback | CONSOLIDATE with same-contract tool and governance parity | No sampled authenticated turn-to-tool trace | **RETIRE BLOCKED** |
| Alternative voice HTTP/PCM transport | KEEP until client/renderer compatibility and acoustic traces | No STT→model→TTS→playback acceptance evidence | **RETIRE BLOCKED** |
| Agent/play/workflow execution variants | KEEP canonical contracts, reconcile durable engines | AST edges only; shared correlation not propagated across all paths | **RETIRE BLOCKED** |
| Connector catalog/readiness/executor | KEEP and VERIFY tenant-ready tool and approval semantics | No runtime action-level authorized provider observation | **RETIRE BLOCKED** |
| Workflow/run dual-write and review status | KEEP, versioned status contract staged | Production DB identity and downstream read models unconfirmed | **RETIRE BLOCKED** |
| Domain-event outbox and relay | KEEP critical durability path | Opt-in dispatch hooks committed, not yet production-observed | **NO RETIREMENT** |
| Temporal worker and async schedulers | AUDIT until worker registration, active queues and restarts proven | Source registry identified, active worker not attested | **RETIRE BLOCKED** |
| Separate Railway frontend and Redis | KEEP until service consumers and cost confirmed | Production ownership and dependency trace not exhaustive | **RETIRE BLOCKED** |

**Approved destructive retirements: zero.**

## Required remaining implementation

1. Inspect Gate 19 independent CI and full CI on the actual new head, repair confirmed failures and rerun; don't treat older-head passes as current.
2. Complete end-to-end typed correlation propagation: ingress request/turn → agent/play/workflow selection → tenant-scoped connector authorization → provider observation → canonical terminal outcome → durable event consumption, preserving idempotency and cancellation. Instrument no payloads, no raw IDs, no plaintext transcript, no provider tokens.
3. Review production telemetry enablement as a separate change; prove retention, consent, access, operational costs and safe off-switch. On approved deployment, collect real span/event evidence and reconcile source graph with authenticated production samples.
4. Verify exact Railway production-to-Supabase project identity through nonsecret project-ref attestation. Do not assume which listed Supabase project is production. Evaluate event/approval consumers only against attested environment.
5. Revisit each retirement candidate with caller coverage, production usage, migration proof, matching tenant/write-fence tests, rollback and reviewer signoff. Until then **no deletion**.

PR stays DRAFT. No merge, deploy, schema mutation or historical reconciliation is authorized by this document.
