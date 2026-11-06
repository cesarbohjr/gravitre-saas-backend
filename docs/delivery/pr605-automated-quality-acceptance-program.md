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
