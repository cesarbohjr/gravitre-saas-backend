# Autonomous Agents — Full Suite Engineering and Release Contract

Status: **Engineering workstream opened; NOT deployed or certified.**

## Architecture baseline
- Reuse `backend/app/services/autonomous_execution_loop.py`, `autonomous_budget_service.py`, canonical action catalogs, E5 execution plans, durable journal/approval fences and connector execution.
- Historical limitations are documented in `docs/delivery/gravitre-autonomous-execution-reaudit-2.0.md`: the preflight/parameter compiler was partial and older ReAct routes bypassed it. Treat historical counts and production evidence as stale until remeasured.
- PR #581 owns browser/native-adapter details; PR #587 owns shared intelligence/voice. This PR owns orchestration of **bounded autonomous task lifecycle** above those layers, not duplication of them.

## Ordered engineering gates
1. **Runtime census:** Inspect actual main and ongoing PRs; trace every ingress (chat, voice, scheduled, workflow, API), routing fork and action dispatch to a single canonical execution/approval/fence path. Produce an executable gap matrix.
2. **Task contract:** Define a versioned, tenant-scoped autonomous goal/plan/step/observation schema with owner, delegated role, tool capability, provenance, dependencies, deadline, budget, approval policy, idempotency key and terminal outcome. Persist state transitions and correlation IDs.
3. **Planner/executor:** Add bounded plan/execute/verify/replan, capability-first tool choice, typed argument compilation and trusted preflight for the agreed scope. Distinguish READ from high-impact WRITE; fail closed on missing grants/consent. No unbounded loops or silent write retries.
4. **Long-running lifecycle:** Support paused/waiting/approval states, controlled resumptions, retry/timeout limits, schedule/event triggers, cancel/revoke, safe handoffs, broker crash/restart and durable progress summaries. Reconcile external side effects before replay.
5. **Workspace UX:** Clear create/run/pause/resume/cancel screens, planned steps and required connectors, budget controls, permission prompts, step-level logs, failure explanations, history and MSP tenant segregation. Chat and voice must accurately report progress without inventing completions.
6. **Security and evaluations:** Authorization at every dispatch, cross-tenant RLS, credential isolation, independent write-fence audit, duplicate-write prevention, adversarial prompt-injection tests, cancellation race, budget exhaustion and provider outage recovery. Include deterministic/no-paid-provider certification; label paid/live evaluation gaps accurately.
7. **Release:** Exact-head CI, migration/rollback, explicit isolated-tenant E2E and controlled progressive deployment. Keep external writes opt-in and approval governed; require separate production activation decision.

## Acceptance matrix (minimum)
- Natural-language goal → typed plan → executable/readiness-scoped tool choice.
- Multi-step read task, missing connector, ambiguous resource, stale permission, denied approval.
- Write approved once; cancellation before write; revocation during execution; crash before/after committed effect; lost ACK; restart/replay with **zero unauthorized or duplicate effects**.
- Budget/token/spend exhaustion; dependency failure; timeout; user-visible truthful state.
- Concurrent tenants and MSP client boundary checks.
- Matched text and voice handoff, interruption and governed write evidence.

## Completion evidence
Commit SHA; action schema provenance; per-test outputs and failure categories; independent external write counter where applicable; CI run links; any skipped/inapplicable cases recorded separately. No claim of autonomy readiness from docs or unit-test coverage alone.

## Boundaries
Do not re-own Agency Agents packaging, PR #581 native runtime, PR #587 One Brain, or PR #590 Qualified Prospecting. Do not merge or deploy without passing applicable certification and review.

## PR #597 merge-reconciliation checkpoint (2026-11-02)
- Merged latest `main` into the PR branch without a force push; preserve frontend marketing changes and autonomous backend certification code.
- The isolated PostgreSQL/Redis and independent-receiver recovery gate passed on pre-reconciliation SHA `665b5b3dc92827d8f8ba4531e4f73f35c0bf98a2`.
- Certification must be rerun against the new reconciled head. A queued, skipped, or approval-blocked run is not evidence of a pass.
- Full product/UX and live-provider certification remain distinct from these isolated test gates; no production deployment or merge is authorized by this checkpoint.
