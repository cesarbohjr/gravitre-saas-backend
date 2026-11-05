# PR #605 — Gate 2: canonical ownership and retirement decision register
Date: 2026-11-04. Baseline: production commit `557be844f191767ea51c9f1d1d4958e5b046ca53`.
Status: **partial static dependency classification**. A KEEP decision means preserve its semantics during migration, not that the implementation is perfect. RETIRE CANDIDATE is not deletion approval.

## Newly confirmed architecture facts
- `backend/app/services/unified_turn_classical_fallback.py` explicitly directs certain LIVE turns to the classical ReAct/governed pipeline and still includes **phrase-pattern safety-net triggers** for connector status, knowledge, Slack posting, Apollo list creation, etc. This is a concrete split-routing mechanism, not merely a historical design note. Risk: wording-sensitive routing and inconsistent customer experiences. **Target: CONSOLIDATE** into structured intent/capability signals, with parity tests before deleting the classical path.
- `backend/app/services/unified_turn_fallthrough.py` enumerates fallthrough reasons including `defer_classical_tool_sse`, `read_tool_classical`, `outcome_error`, `false_connector_disconnect_claim`, `write_plan_unavailable`. **Target: UPGRADE** to explicit typed transition/failure outcomes, preserving honest errors and governed execution. Distinguish intentional authorized delegation from hidden downgrade.
- `backend/app/operators/react_engine.py` implements an active-looking reason/act/observe loop with tool registry, guardrails and audit. It also contains serial-tools A/B settings. **Target: CONSOLIDATE**, NOT immediate deletion: the classical loop may currently supply tool SSE, safety or capabilities missing in LIVE.
- `backend/app/connectors/connector_availability_service.py` declares itself canonical source of connector availability, health and execution readiness. **Target: KEEP + VERIFY** all tool discovery paths consult it for tenant/scope/action readiness.
- `backend/app/services/execution_plan_authority.py` explicitly protects terminal write-plan truth from weaker follow-up compose/ReAct state. **Target: KEEP contract, UPGRADE integration**. Removing it prematurely risks fabricated or overwritten completion.
- `backend/app/services/execution_outcome.py` documents one terminal-outcome authority but also a **deliberate dual-write** through repository into `workflow_runs` and `runs/run_steps`; audit events also dual-write into `audit_logs` and `audit_events`. **Target: KEEP canonical outcome contract, CONSOLIDATE storage only after consumer/read-model and migration evidence**. Dual-write is not automatically an obsolete fallback.
- `backend/app/services/unified_turn_pipeline_bridge.py` bridges LIVE latency stages into shared performance telemetry; tracks both LIVE and classical stages. **Target: KEEP telemetry semantics, UPGRADE** to a unified span/trace schema.
- Static inventory at production baseline: ~177 voice-related files, ~48 named orchestration/memory files, ~211 connector-related files, ~115 workflow/execution-related files (overlapping name-based buckets, include tests; **not** counts of active components). These establish investigation scope, not production usage.

## Decision register — controlled migration
| ID | Component/contract | Current classification | Target action | Critical dependency / removal gate |
|---|---|---|---|---|
| DEC-001 | LIVE→classical phrase-triggered routing | Confirmed in source, live invocation unverified | CONSOLIDATE | Inventory callers and active flags; prove structured intent/tool parity for connector status, KB, Slack, Apollo, plan-before-tool |
| DEC-002 | ReAct engine | Present; active callers not yet mapped | CONSOLIDATE / RETIRE CANDIDATE | Preserve tool SSE, approvals, audit, multi-step recovery, cancel and governance |
| DEC-003 | LIVE fallthrough reason enum | Present | UPGRADE | Replace ambiguous fallback with typed explicit delegation/error; test each reason |
| DEC-004 | Connector availability authority | Present | KEEP + VERIFY | Tenant scopes, OAuth readiness, native/Nango precedence, action-level permission |
| DEC-005 | ExecutionPlan terminal-write authority | Present | KEEP + INTEGRATE | No regression of persisted terminal outcome, approval or cancellation |
| DEC-006 | Canonical execution outcome | Present | KEEP + VERIFY | No independent terminal writers; exact verified result and idempotency |
| DEC-007 | workflow_runs↔runs/run_steps repository mirror | Documented dual-write | CONSOLIDATE CANDIDATE | Audit readers, historical records, migration, rollback and correctness before schema change |
| DEC-008 | audit_logs↔audit_events | Documented dual-write | KEEP pending evidence | Retention, analytics, audit compliance and reader dependencies |
| DEC-009 | Unified latency bridge | Present | UPGRADE | Preserve observability and cross-provider attribution |
| DEC-010 | Voice Pipecat/client transcript relay | Present | UPGRADE | Verify actual duplex entry point, STT finalization, browser state, echo, barge-in and TTS PCM |
| DEC-011 | Memory/context variants | Multiple named modules | AUDIT | Identify source of truth, actual consumers, privacy and temporal semantics |
| DEC-012 | Agent/play/workflow execution engines | Multiple named modules | AUDIT | Prove active execution routes, approvals, durable runs and verified outcomes |
| DEC-013 | Vercel + Railway frontend projects | Both present | AUDIT | DNS/traffic/deployment ownership before retiring either |
| DEC-014 | Deepgram/ElevenLabs/LLM provider adapters | Present by prior inspection | AUDIT | Verify deployed configuration, latency, usage, costs, auth and fallback policy |

## Critical regression suite to implement before removing classical routing
1. Connector inventory query paraphrases and follow-ups, connected/disconnected/insufficient-scope cases.
2. Read an authorized Gmail message or equivalent; ensure real tool invocation and verified observation, not a textual plan.
3. Propose a Slack write and Apollo list creation with correct approval, denial, revocation, and no unauthorized write.
4. Knowledge base retrieval with citations and negative/no-evidence case.
5. Multi-step plan-before-tools, idempotent replay, process restart and interruption.
6. Model unavailable, tool unavailable and degraded provider: typed truthful failure, no silent chat-only downgrade.
7. Text/voice semantic parity and transcript deduplication, cancellation, stale-turn suppression.
8. Persisted terminal outcome must not be overwritten by follow-up composition.
9. All relevant tenant isolation and audit invariants.

## Remaining gate blockers
Full call graph, active production flags, deployed route configuration, provider credentials readiness (never expose secrets), actual customer telemetry, model/voice minutes and costs, all 13k-tree module ownership, exhaustive CI coverage, and measured regression results remain outstanding. Do not claim completed holistic audit or safe deletion.

## Gate 17 — bounded dynamic-dispatch discovery and production ownership checkpoint (2026-11-05)

**Status: NOT RETIREMENT-CERTIFIED.** Existing source code and sampled runtime evidence do not establish every active caller. Added `backend/scripts/pr605_cross_surface_ownership_inventory.py` and offline tests `backend/tests/scripts/test_pr605_cross_surface_ownership_inventory.py`; independent workflow `.github/workflows/pr605-cross-surface-ownership.yml` generates a SHA-pinned, retained JSON artifact for ten critical source candidates. It extracts static import references, literal API paths, selected dynamic import/getattr candidates and non-sensitive environment variable *names*, with explicit unknowns. **These are not dynamic execution traces**, and the exporter deliberately sets `retirement_certified=false`. A passing workflow certifies only this bounded evidence scope.

### Newly refined source-grounded ownership decisions

| ID | Source chain / finding | Proposed action | Retirement blocker / acceptance |
|---|---|---|---|
| DEC-015 | Browser `pipecat-voice-client.ts` builds authenticated/org-scoped WS URL, selecting `NEXT_PUBLIC_VOICE_WS_BASE`, `NEXT_PUBLIC_BACKEND_WS_URL`, voice-status hint or production API origin; literal `/api/voice/pipecat/ws` | KEEP and VERIFY runtime selection | Prove actual production origin, WS auth, session owner, audience, reconnect/cancel and fallback browser compatibility |
| DEC-016 | Next.js `app/api/voice/session/turn/route.ts` forwards NDJSON to `/api/voice/session/turn` using `voiceFastApiBase()`, retaining authorization/org/environment headers through helper | KEEP routing contract; UPGRADE origin observability | Browser→Vercel→Railway target and auth/tenant context, correct deployed SHA; no silent localhost in production |
| DEC-017 | `voice-api-proxy.ts` gates on configured `FASTAPI_BASE_URL` but delegates configured value to `backendBaseUrl()`; absent env falls back to localhost:8000 | VERIFY/UPGRADE | Resolve actual environment and `backendBaseUrl()` precedence; test production and preview config with sanitized base identity before changing routing |
| DEC-018 | `unified_turn_classical_fallback.py` keeps a reduced phrase-pattern safety net and structured `needs_tool_sse` defer; `connector_tool_proposal` explicitly stays LIVE | CONSOLIDATE CANDIDATE only | Map request branches and runtime flags; protect connector SSE, tool observations, approvals and no false tool success before removing classical |
| DEC-019 | `execution_outcome.py` documents one terminal writer with repository-level `workflow_runs`→`runs` mirroring; audit dual-write deliberately retained | KEEP canonical write contract | Prove all actual writers/readers, durable outbox, event subscribers, approval domains and transition consistency; no premature one-table cutover |
| DEC-020 | Source-only caller inventory added in PR #605 identifies ten focused sources and selected literal routes, with unknown dynamic call dispatch | KEEP investigation tooling | Extend to Next.js component callsites and backend method bodies, RPC/event subscribers; prove real request coverage and owner signatures for every proposed retirement |

**Evidence and semantics:** `registered route` ≠ `actively called production path`; `imports module` ≠ `invokes method`; `provider configured` ≠ `tenant authorized and executed`. Classify ambiguous paths as UNKNOWN until traffic, spans and write-fence tests demonstrate behavior. No current candidate is certified for deletion.

### Release sequencing
1. Run the dedicated source-only ownership workflow on its triggering PR head and inspect artifact/test logs; repair any source extraction errors, preserving SHA identity.
2. Complete H-01 dynamic frontend/backend routing and H-03 governed execution with source and trace-linked ownership; H-04 voice trace, H-05 database event consumers, H-06 production project-ref proof and H-07 latency/cost evidence remain blockers.
3. Move specific retirement candidates to `RETIRE APPROVED` **only** after source callers, production usage, equivalent consumer migration, security tests, owner signoff and rollback are recorded. No blanket approval is implied.
4. After holistic audit closure, certify full CI on the new exact head and independently verify production DB identity, then seek the protected merge/release gates. Historical reconciliation remains separately authorized.
