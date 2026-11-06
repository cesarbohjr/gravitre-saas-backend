# Gravitre — Automated Quality & Acceptance Program (Master Plan Phase 0)

**Status:** implementation specification; tests not yet certified. This precedes major architecture changes and complements Gate 27.

## Goal
Measure ChatGPT-class conversational quality, speed, and tool initiative alongside Gravitre's business automation and autonomous execution reliability. Benchmark observed behavior, not undisclosed ChatGPT internals.

## Cost and safety
Default CI uses synthetic tenants and local provider mocks; no production secrets, paid LLM calls, external provider writes, or permanent staging environment. GitHub Actions minutes and artifact storage can still incur charges: review account quotas and budgets before enabling schedules. Block unexpected outbound requests. Never equate mocked provider behavior with live integration certification.

## Coverage and required proof
| Area | Synthetic journeys and failure modes | Evidence |
|---|---|---|
| Chat and model routing | fast direct answers, deep reasoning, multi-turn context, memory relevance, streaming, fallback, policy, hallucination checks | response evaluation, model-call count, TTFT and p95 |
| Voice | transcription, synthesis, interruption/barge-in, reconnection, audio buffering, transcript duplication, voice/text parity | audio fixtures, event traces, first-audio latency |
| Agent autonomy | objective decomposition, plan selection, tool discovery, bounded delegation, stopping conditions, recovery, no fabricated completion | step traces, verified effects, task-success rubric |
| Business enterprise automation | lead qualification, CRM updates, campaign reporting, customer support triage, approvals, cross-app handoffs, scheduled plays, multi-step workflows | synthetic organization journey, state changes across apps |
| Connectors and identity | native/Nango paths, consent, expired/revoked OAuth, rate limits, async acceptance, uncertain outcomes, duplicate callbacks, tenant-scoped permissions | mock request ledger, authorization decisions |
| Workflows / event consumers | cancellations, retries, compensation, concurrency, idempotency, PostgreSQL outbox, replay, DLQ, eventual consistency | disposable PostgreSQL persisted state |
| Billing and entitlements | Stripe-style signed test fixtures, checkout lifecycle, invoices, subscriptions, upgrades/downgrades, dunning, duplicate/out-of-order webhooks, usage limits | durable ledger and entitlement assertions |
| Security and governance | tenant isolation, RBAC, human approval, prompt injection, PII/secret redaction, audit logs, speculative writes | negative-path tests and sanitized evidence |
| Web and API | browser journeys, auth, accessibility, API contract drift, failures, responsiveness | Playwright and contract reports |
| Reliability and operations | migration safety, rollback, concurrency, latency/cost budgets, fault injection, provider outage | reproducible CI results and release ledger |

## Automation architecture
1. **PR fast gate:** lint, unit, contracts, authorization and routing tests; deterministic and bounded.
2. **PR integration gate:** disposable PostgreSQL/Redis where needed, local fake connectors, signed webhook fixtures, outbox/consumer replay, billing and agent end-to-end journeys.
3. **PR UI/voice gate:** Playwright browser journeys and prerecorded synthetic audio; assert state, not screenshots alone.
4. **Evaluation gate:** versioned prompt and agent trajectory datasets with human-reviewed reference rubrics; deterministic assertions always gate, stochastic quality scores use calibrated thresholds and repeated trials. Start with one evaluation framework (Promptfoo *or* DeepEval) after evaluating existing test infrastructure.
5. **Nightly/manual extended gate:** larger synthetic scenarios, concurrency, resilience and performance; only after Actions budget and quotas are checked.
6. **Release evidence:** per-commit matrix, run links, failure classification, known untested surfaces, baseline deltas and explicit go/no-go recommendation. No automated merge or production deploy.
7. **Post-approved-deployment:** tightly controlled production smoke tests with synthetic accounts and explicit authorization; never assume mock success proves provider integration.

## Acceptance policy
- No skipped critical suites, unverified external writes, silent fallbacks, or false successful agent statuses.
- Each critical enterprise journey verifies permissions, intermediate state, external-call intent, downstream effects, final state and safe retry.
- Capture p50/p95 time-to-first-token, first-audio, end-to-end task duration, model/tool calls, cost estimates, and answer/trajectory quality; set numeric thresholds only after baseline measurement.
- Maintain traceable mapping from every major runtime surface to owner, test, workflow, and release gate.
- Existing Gate 26 isolated PostgreSQL acceptance and connector governance are foundations; inventory all other existing tests before adding overlapping frameworks.

## Ordered engineering backlog
P0: inventory existing workflows and tests; identify blind spots and actual Actions cost exposure.
P1: synthetic fixture factory, network egress guard, deterministic provider simulators (CRM, Nango/native OAuth, Stripe, messaging, ads, analytics), disposable data services.
P2: agent/play/workflow and enterprise cross-app acceptance journeys with durable outcome assertions.
P3: chat/model/voice benchmark dataset and browser/audio acceptance.
P4: CI orchestration, artifacts, failure triage, coverage ledger, performance budgets.
P5: controlled post-deployment production smoke tests only after separate approval.

## Definition of done
A pull request cannot claim full certification until required suites pass on its exact head, all critical journeys have persisted-effect assertions, missing coverage is explicitly listed, and release approval remains separate. No claim of zero monetary cost or production equivalence.

## GitHub Actions rationalization and Master QA naming (mandatory Phase 0 gate)
Before adding more workflows, inventory **every** `.github/workflows/*.yml` and `*.yaml` file and its triggers, branch/path filters, required-check status, ownership, dependencies, last meaningful run, average duration, artifacts, secrets, external network access, and estimated runner-minute/storage consumption. Include reusable workflows and workflow_call dependencies. Produce a versioned workflow inventory and explicit KEEP / CONSOLIDATE / RETIRE / INVESTIGATE disposition with evidence.

- **KEEP** active merge protections, security scanning, migration safety, deployment controls, and specialized tests that have distinct value.
- **CONSOLIDATE** overlapping jobs and repeated installs into reusable workflows/composite actions while preserving independent required status checks, path coverage, and failure isolation. Do not create one enormous un-debuggable job.
- **RETIRE** obsolete or superseded workflows only after proving no callers, required branch-protection references, deployment triggers, or release dependencies remain. Prefer a reviewable deletion PR with rollback instructions; do not delete existing workflows automatically as part of the inventory.
- **INVESTIGATE** unknown or infrequently triggered workflows; inactivity alone is not proof of irrelevance.
- Never weaken protections or remove a required status check without separately reviewing branch rulesets, deployment protections, and the replacement check.

Proposed clearly labeled master sequence (names provisional until inventory):
1. `QA 00 — Change Scope & Contract Checks`: fast PR lint, static analysis, unit tests, schemas and policy.
2. `QA 10 — Synthetic Integration & Data Durability`: disposable PostgreSQL/Redis, billing webhooks, event relay, retries, tenant isolation.
3. `QA 20 — Agent, Play & Enterprise Workflow Acceptance`: simulated CRM, marketing, support, connector OAuth and authorization, persisted outcomes.
4. `QA 30 — Chat, Model & Voice Quality`: text/voice regressions, latency and deterministic evaluations; optional calibrated model-based evals only with cost approval.
5. `QA 40 — Browser & API End-to-End`: Playwright and API journeys against ephemeral local app processes.
6. `QA 50 — Extended Reliability`: manual/nightly fault injection, concurrency, recovery and performance with configured budgets.
7. `QA 90 — Master Release Evidence`: collect exact-head results, distinguish missing/skipped/cancelled from passed, publish audit artifacts and block certification on required failures.

Prefer one clearly named entry workflow invoking smaller reusable jobs; maintain explicit individual status checks and clear ownership. Configure concurrency cancellation, least-privilege permissions, bounded timeouts, path filters only where safe, artifact retention limits, dependency caching, and no live credentials. Verify that required jobs do not disappear under path filtering. Keep production deployment separate from QA automation and approval-gated.

**Exit criteria:** workflow inventory complete; approved dispositions recorded; legacy checks mapped to replacements; branch protections checked; master QA labels consistent; reduced duplicate CI work measured; no loss of security, integration, or release coverage.
