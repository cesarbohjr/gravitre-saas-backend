# Gravitree — Complete Six-Phase Engineering, Multimodal Parity and End-to-End Acceptance Plan

**Document type:** Implementation plan, PR scope, test specification and release-gate contract  
**Target repository:** `cesarbohjr/gravitre-saas-backend`  
**Target branch:** `main` through reviewed PRs  
**Status:** Proposed engineering plan; not an assertion that all work is complete  
**Primary objective:** Prove that Gravitree's text, speech, intelligence, Plays, Workflows, connectors, governance and learning form one reliable, measurable end-to-end product.

## 1. Executive decision

This is **not just a testing project**. It has four linked deliverables: (1) audit the existing implementation, (2) build or repair missing connections, (3) test realistic complete user journeys, and (4) prove production behaviour with traceable evidence. The six-phase framework remains the organizing structure. Provider optimization and humanlike conversation are mandatory parts of Phases 3–4, not deferred enhancements.

Do not declare parity with ChatGPT or Claude based on CI passing, vendor marketing, or scripted audio. Parity is an **evidence-based comparison** by dimension and modality. ChatGPT and Claude may expose different voice capabilities; document comparable and non-comparable modes.

### Known starting point and caveats

- PR #559 was merged to `main` at commit `e1d0cd0`; Railway subsequently reported a successful backend redeployment of that commit.
- Existing offline 12-scenario Phase 3 evaluation, Phase 5 prerequisite gates and Snowflake isolated dependency audit passed during that release.
- These facts do **not** establish that all 26 model entries are active, that all seven intelligence capabilities influence every relevant path, or that live conversational and provider outcomes have been verified.
- Repository evidence previously identified Deepgram Nova-2 on an HTTP STT path, Deepgram Flux (`flux-general-en`) on a Pipecat path, ElevenLabs Flash v2.5 as a live TTS default, and Pipecat voice orchestration. **Reinspect current code and live configuration** before making changes; model identifiers and provider features can change.
- Preserve the canonical `CognitiveTurnKernel`/existing execution, intelligence, policy and connector paths. Do not introduce a second reasoning or authorization engine.

## 2. Non-negotiable architecture and safety contracts

**Canonical journey:** User input → modality adapter (ASR if needed) → session/identity/tenant context → intent and memory → seven-capability intelligence router (relevant capabilities only) → canonical reasoning/planning → Play/Workflow selection → policy/approval → connector execution → independent readback/outcome verification → eligible learning signal → response composition → TTS/playback if requested.

1. **One brain, multiple modalities:** Text and voice must use the same reasoning, memory, governance and execution contracts. Presentation can differ, authority cannot.
2. **No write before authorization:** Speech interruption, correction, revocation or cancellation must block the external write itself, including race conditions; suppressing the spoken response is insufficient.
3. **Prove side effects:** A successful tool call or generated narrative is not proof that an external state changed. Verify via independent readback or a trusted provider receipt with an explicit confidence classification.
4. **No indiscriminate intelligence activation:** Seven capabilities must be available and appropriately routed; not every user turn should invoke all seven.
5. **No premature learning:** Training requires consent, sufficient eligible data and measurable outcome attribution. Keep dormant/scaffolded/loaded/trained/serving states distinct.
6. **Tenant and privacy boundaries:** Every retrieval, model inference, tool, Play, Workflow, evidence record and learning update is tenant-scoped.
7. **Test safely:** Use isolated test tenants, sandbox provider accounts, reversible operations, fake data and dry runs. Production smoke tests must be non-destructive unless separately approved.
8. **No silent fallback:** If a model, connector, live provider or approval gate is unavailable, surface the real limitation and mark the test blocked or failed.

## 3. Phase 1 — Audit the 14 original and 12 advanced ML models

### Engineering work

- [ ] Inventory all 26 catalog entries, owning module, intended task, input/output schema, artifact location, deployment status, serving endpoint, router reference, fallback and training eligibility.
- [ ] Confirm each of the original 14 models can load a real artifact and execute a representative inference, or explicitly classify it as not operational.
- [ ] Verify the 12 advanced models are correctly scaffolded, gated and dormant until data, consent and prerequisites exist. Do not mislabel dormant as production-active.
- [ ] Validate missing-artifact, malformed-input, timeout, degraded-model, stale-feature and unavailable-provider fallbacks.
- [ ] Inspect privacy boundaries, federated-learning consent, feature provenance, model-version logging and tenant isolation.
- [ ] Repair verified missing inference/serving paths; do not create duplicate model registries or inference engines.

### Required evidence

A versioned `model_readiness.json` with model ID, artifact hash/version, load result, inference fixture, measured latency, serving status, fallback test, consent/training gate, owner and linked CI job. **Exit gate:** all 26 entries accurately classified; no model represented as working without proof; release-critical serving paths pass.

## 4. Phase 2 — Integrate the seven intelligence capabilities

Capabilities: **sentiment, contextual, causal, temporal, relational, adaptive and predictive**.

### Engineering work

- [ ] Map producers, router invocation rules, inputs, outputs, confidence and downstream consumers for each capability.
- [ ] Prove contextual intelligence uses permitted organizational data and current session context; sentiment informs tone but does not overrule intent or permissions.
- [ ] Prove causal claims require suitable outcome/intervention evidence and are distinguished from correlation.
- [ ] Prove temporal and relational signals respect timestamps, entity identities, source provenance and tenant boundaries.
- [ ] Prove adaptive and predictive outputs are measurable, calibrated and do not silently trigger autonomous writes.
- [ ] Instrument which capabilities were eligible, invoked, skipped, errored and actually consumed by planning, response, Play or Workflow logic.
- [ ] Verify text and voice entry points, Plays and Workflows use the **same** capability router and governed decision contracts.
- [ ] Repair broken wiring, duplicated logic or discarded intelligence outputs.

### Required evidence

`intelligence_coverage.json` with per-capability invocation/consumption traces and negative tests. **Exit gate:** each capability has at least one positive and one negative scenario; relevant outputs demonstrably affect downstream behaviour; no tenant leaks or governance bypass.

## 5. Phase 3 — Text, speech and conversational evaluation

### Four required interaction modalities

1. **Text → Text:** Typed request through reasoning and optional tool/Play/Workflow execution to a typed result.
2. **Voice → Text:** Speech recognition through the canonical reasoning/execution path to a written response.
3. **Text → Voice:** Typed request through canonical reasoning and expressive speech synthesis/playback.
4. **Voice → Voice:** Spoken request through ASR, reasoning, authorized execution when requested, streaming TTS, playback, interruption and recovery.

Test each modality in **answer-only, read-only tool, authorized write, denial/cancellation and failure/recovery** variants. Also test mixed-mode continuity (switch from voice to text mid-task and back).

### Conversational styles and representative prompts

| Style | Example prompt | Acceptance focus |
|---|---|---|
| Professional | “Summarize the client's outage and the safest next action.” | Accuracy, concise confidence, restraint |
| Casual | “Hey Nora, what's happening?” | Natural, relaxed register |
| Social | “I'm thinking about a weekend getaway.” | Appropriate curiosity, non-repetitive follow-up |
| Jovial | “We just signed our biggest customer!” | Warm, proportionate enthusiasm |
| Humorous | “My laptop decided to retire early.” | Recognizes joke, timing, useful transition |
| Playful | “Are you going to beat me at troubleshooting?” | Light banter without losing task focus |
| Empathetic | “I've had a terrible day dealing with outages.” | Sensitive response, no forced cheer |
| Reflective | “Should we change our pricing strategy?” | Thoughtful pacing and substantive reasoning |
| Surprised | “The system recovered without intervention!” | Contextual surprise, cautious inference |
| Storytelling | “Tell me a funny story about a help desk.” | Varied rhythm and engaging delivery |
| Mixed emotion | “That was hilarious. Anyway, we have a security breach.” | Immediate serious tone shift |
| Frustration | “This is the third time it broke.” | Calm acknowledgment and effective action |
| Long conversation | “Continue our incident review from ten turns ago.” | Accurate memory and entity continuity |
| Correction | “No, I meant the other customer.” | Reground entity and avoid stale action |
| Interruption | “Stop—don't send that email.” | Immediate audio stop **and** write prevention |
| Deliberation | “Give me two options and explain the trade-offs.” | Reasoning quality, natural pauses |

### Humanlike speech quality requirements

Evaluate pitch, emphasis, intonation, rhythm, speaking rate, turn timing, silence, hesitation, chuckles, laughter, sighs and breaths **where the selected provider supports them and the context warrants them**. Do not insert arbitrary sound effects or portray generated vocalization as a genuine physiological or emotional state. A “smirk” is a subtle vocal style, not an audio file. Serious incidents, security events, grief and high-stakes decisions require restrained delivery. No repetitive stock phrases, fake enthusiasm or unwanted fillers.

### Instrumentation and measurement

Capture: audio capture start, ASR partial/final, endpoint detection, intent ready, memory/context ready, intelligence router complete, first LLM token, plan/approval, tool start/finish, independent readback, first TTS chunk, first audible playback, final playback, interruption onset, audio stopped, cancellation/write-gate decision. Report median, p90, p95, error rates and sample sizes, not only a single average. Record ASR word error rate for reference clips, response factuality, multi-turn retention, tool correctness, task completion, naturalness and speaker-rated emotional appropriateness.

### Comparative parity study

- Use equivalent scripted prompts, environments and language; record reference model, date, voice mode and settings.
- Blind-rate randomized clips and anonymized text with multiple raters using a predefined 1–5 rubric; collect inter-rater agreement and failure comments.
- Compare text reasoning and voice expressiveness separately. Compare tool execution only where product capabilities are genuinely comparable.
- Publish per-dimension differences and confidence limits; **do not claim full parity unless every predeclared applicable gate passes**.

**Exit gate:** All modalities and dialogue categories have reproducible results; live versus simulated results clearly separated; serious defects enter Phase 4.

## 6. Phase 4 — Provider capability optimization and targeted repairs

### Audit the deployed configuration first

- [ ] Inspect Railway runtime flags and actual provider/model overrides without exposing credentials.
- [ ] Inspect Deepgram Nova/Flux usage by endpoint, Flux turn-taking and resumption configuration, audio sample rates and streaming behaviour.
- [ ] Inspect ElevenLabs Flash v2.5 defaults, available supported expressive models, streaming transport, voice selection, stability/style controls and provider-specific expressive features.
- [ ] Check the installed Pipecat version and supported provider APIs; identify outdated code, deprecated aliases and unused features.
- [ ] Check provider account plan, API access, rate limits, voice licensing, concurrency, cost and live test eligibility.
- [ ] Review newer ElevenLabs and Deepgram agent/realtime offerings as **capability references**, not replacements for Gravitree's canonical brain or write governance.

### Benchmark before changing defaults

Run an A/B matrix: current production baseline versus each **verified available and compatible** candidate. For each candidate measure ASR quality, endpointing, interruption response, first audio, complete latency, expressiveness, error rate, concurrency and cost per successful task. Evaluate Flash/expressive model trade-offs; newer is not automatically better. Model IDs such as “V4 Turbo” must not be assumed valid without vendor confirmation.

### Implementation sequence

1. Preserve a baseline fixture and deployment config snapshot.
2. Introduce provider capability negotiation/configuration behind reversible flags.
3. Improve expressive delivery selection using sentiment, contextual intent and conversation state; never bypass safety or force emotions.
4. Optimize streaming/latency, buffering, endpointing and interruption propagation with measurable before/after traces.
5. Repair verified router, memory, Play/Workflow or connector wiring gaps.
6. Add unit, contract, integration, browser and provider-backed regressions for each fix.
7. Canary and roll back if quality, cost, safety or reliability deteriorate.

**Exit gate:** Changes outperform baseline on agreed metrics without failing any governance or regression test; unsupported candidates remain disabled.

## 7. Phase 5 — Plays, Workflows, connectors and governed learning

### Plays and Workflows must be first-class E2E paths

- [ ] Inventory all active Play categories and Workflow trigger/execution types; identify owners, action schemas and backend/frontend surfaces.
- [ ] Prove text and voice can discover, select, parameterize, preview, approve and execute relevant Plays.
- [ ] Prove Play → Workflow and Workflow → connector handoffs preserve org/client/department scope, intelligence context, authorization, audit and outcome IDs.
- [ ] Verify retries, timeouts, deduplication, idempotency, partial failures, compensation, human approval waits and resume behaviour.
- [ ] Confirm the intelligence layer influences planning when appropriate, rather than merely appearing in a UI badge.
- [ ] Test multi-step scenarios using actual permitted test connectors and independent readback.

### Governed learning cycle

**Required sequence:** Consent/eligibility → authorized intent → planned action → explicit approval → external write → independent readback → measured outcome → attributed learning record → repeated comparable turn → demonstrable improvement.

- [ ] Validate training opt-in, data sufficiency and model activation gates.
- [ ] Verify late tool results cannot resurrect cancelled work.
- [ ] Verify correction after an approval prompt invalidates the previous action target before commit.
- [ ] Verify failed/ambiguous outcomes are not converted to successful learning labels.
- [ ] Test tenant isolation, consent revocation and deletion/retention policies.

**Exit gate:** One or more real provider-backed, test-tenant learning cycles show independent verification and repeat-turn measurement; no unauthorized side effects.

## 8. Mandatory E2E scenario matrix

| ID | Scenario | Required systems and pass evidence |
|---|---|---|
| E01 | Text → Text Q&A | Memory, router, reasoning, typed response |
| E02 | Voice → Text Q&A | Mic, ASR, router, reasoning, typed response |
| E03 | Text → Voice Q&A | Router, reasoning, TTS, audible playback |
| E04 | Voice → Voice conversation | ASR, turn-taking, reasoning, streaming TTS, barge-in |
| E05 | Text → Play read-only | Play selection, contextual intelligence, tool read, truthful answer |
| E06 | Voice → Play approved write | ASR, Play, approval, connector write, independent readback |
| E07 | Text → Workflow | Workflow parameters, steps, retries, results |
| E08 | Voice → Workflow | Spoken trigger, clarification, approval, status narration |
| E09 | Play → Workflow | Shared context, policy, dependency handling, outcome |
| E10 | Workflow → Connector | Tenant isolation, idempotency, external readback |
| E11 | MSP incident across systems | Customer scope, seven-capability eligibility, Play, Workflow, ticket/update verification |
| E12 | Workflow creation from conversation | Natural-language plan, schema validation, dry run, authorized activation |
| E13 | Mixed voice/text correction | Same session and memory, stale target rejected |
| E14 | Seven-capability targeted suite | Positive/negative activation and downstream consumption for each capability |
| E15 | Humour → security incident | Expressive delivery switches immediately to serious and precise |
| E16 | Interrupt before write | Audio stops, authorization invalidated, **zero external writes** |
| E17 | Provider timeout/outage | Safe fallback, truthful error, retry/deduplication |
| E18 | Full governed learning | Approval, write, independent verification, eligible update, repeat-turn gain |
| E19 | Multi-turn social conversation | Natural follow-ups, memory, no hallucinated personal details |
| E20 | Long professional conversation | Stable entities, citations/provenance, accurate decisions |
| E21 | Emotional expressiveness | Laughter/sigh/pause appropriateness, blind listening ratings |
| E22 | Cross-tenant adversarial test | No leakage across models, tools, Plays, Workflows or learning |
| E23 | Revoked approval race | Late provider dispatch blocked, no resurrection |
| E24 | Frontend-to-production smoke | UI, auth, API, database, streaming, connector health |

For each E2E test run a trace of **user input → recognition → intent/context → relevant intelligence → reasoning → Play/Workflow → authorization → connector → independent verification → learning eligibility → output**. Mark stages `executed`, `not applicable`, `skipped unexpectedly`, `failed` or `blocked`. Never treat a polished response as proof of successful backend execution.

## 9. Test infrastructure and CI integration

### Existing-first approach

Extend current Python test suites, Pipecat voice harness, browser Playwright tests, Phase 3 12-scenario runner, Phase 5 evidence gates, GitHub Actions and release smoke tests. Avoid new overlapping test frameworks. Separate:

- **Unit/contract:** Fast deterministic tests on each PR.
- **Integration:** Isolated database and mocked/sandbox providers, scheduled and PR-triggered where practical.
- **Browser E2E:** Actual frontend interactions, audio/playback event simulation and trace assertions.
- **Live-provider acceptance:** Opt-in, budget-controlled, credential-gated, test tenants only; never mislabel skipped as passed.
- **Human listening:** Recorded clips, randomized blind ratings and adjudicated results.
- **Production smoke:** Read-only or explicitly authorized reversible checks after deployment.

### Required evidence artifact schema

Each run must produce structured artifacts including: run ID, commit SHA, deployment SHA, environment, timestamp, test ID, modality, provider/model/version, tenant/test-fixture identifier, expected stages, observed stages, trace/correlation IDs, latency breakdown, authorization decisions, connector side effects, independent readback, intelligence eligibility/invocation/consumption, learning eligibility, assertions, error class, human ratings where relevant, and final verdict `PASS|FAIL|BLOCKED|NOT_RUN`.

Protect secrets, PII, raw customer audio and provider tokens. Publish redacted reports only.

### Suggested GitHub Actions gates

1. `intelligence-model-readiness` — inventory and inference/fallback contracts.
2. `intelligence-seven-capability-coverage` — invocation and consumption traces.
3. `multimodal-e2e-offline` — all four modalities and representative scenarios.
4. `plays-workflows-governance-e2e` — orchestration, write gate and isolation.
5. `voice-provider-compatibility` — capability/config validation, optional sandbox live suite.
6. `governed-learning-evidence` — outcome proof and repeat-turn improvement.
7. `release-acceptance-summary` — aggregates results; **fails closed** for critical failures, reports missing live evidence as blocked.

These are proposed logical gates; adapt existing workflow names and jobs rather than blindly creating duplicates.

## 10. Explicit acceptance thresholds and decision policy

**Before benchmarking**, engineering and product owners must approve numerical targets for latency, ASR error, response quality, human naturalness, interruption stop time, tool correctness and cost. Record targets in a versioned config; do not choose them after seeing results.

**Always-fail security gates:** unauthorized write, approval bypass, cancellation-after-revocation write, cross-tenant leakage, falsified verification, consent violation or sensitive-data disclosure.

**Functional gate:** Each applicable scenario executes the required real stages, with independently observed effects and truthful status. A mocked provider test cannot substitute for a required live-provider gate.

**Parity gate:** Publish per-dimension comparisons against reference systems. Claim “meets target” only when supported by blinded, comparable measurements; otherwise mark partial parity or outstanding gap.

**Release gate:** All required CI green; production-safe smoke green; no critical or high-severity unresolved regressions; rollback verified; live tests either pass or are explicitly recorded as release-blocking where required.

## 11. Delivery plan and PR breakdown

| Order | Deliverable | Dependency | Merge rule |
|---|---|---|---|
| PR-A | Audit baseline, inventory, gap report, trace schema | Current `main` | No runtime behaviour change; evidence reviewed |
| PR-B | Phase 1/2 model and intelligence wiring repairs | PR-A | Tests and isolation pass |
| PR-C | E2E modality, dialogue corpus and telemetry | PR-A | Deterministic harness passes |
| PR-D | ElevenLabs/Deepgram optimization and expressive delivery | PR-C | Baseline A/B evidence, flags and rollback |
| PR-E | Plays/Workflows/connector and cancellation hardening | PR-B/C | Negative write-gate tests pass |
| PR-F | Governed learning and independent outcome verification | PR-E | Real test-tenant proof and consent gates |
| PR-G | Full release acceptance, performance comparison and production evidence | All preceding | Explicit go/no-go and safe deployment |

PR boundaries may be adjusted to minimize conflicts. Never merge a broad consolidation solely because some component tests pass. Rebase and validate against current `main`; inspect migrations and feature flags; preserve existing customer configurations.

## 12. Runbook and ownership

1. Pin current GitHub `main`, Railway deployment and frontend deployment identifiers.
2. Collect repository/configuration evidence and map every requirement to a code path and owner.
3. Implement instrumentation before performance changes.
4. Execute deterministic baseline tests; publish failures and missing coverage.
5. Apply minimal targeted fixes, each with regression tests.
6. Run provider-backed sandbox and human evaluation with approved spend/credentials.
7. Run full Plays/Workflows/learning scenarios and verify external state independently.
8. Review security, privacy, cost and operational telemetry.
9. Merge only green, reviewed PRs; deploy with flags/canary and rollback plan.
10. Execute production-safe acceptance and publish final evidence with a go/no-go decision.

### Blocking dependencies to resolve explicitly

- Live ElevenLabs/Deepgram account capabilities, quotas, current model availability and credentials.
- Safe test-tenant accounts for real connector read/write/readback.
- Test database/migration parity and authorization fixtures.
- Frontend environment/deployment identity and audio browser/device matrix.
- Reference ChatGPT/Claude comparison methodology and blind human raters.
- Preapproved numeric acceptance thresholds and cost ceiling.

## 13. Final definition of done

- [ ] All 26 model entries are accurately inventoried and operational states proven.
- [ ] All seven intelligence capabilities are traced and appropriately consumed.
- [ ] All four modalities pass relevant answer-only, execution, denial and recovery journeys.
- [ ] Professional, casual, social, humorous, playful, empathetic and mixed-emotion dialogue meet agreed quality targets.
- [ ] ElevenLabs/Deepgram configuration is audited and any upgrade is supported by real A/B evidence.
- [ ] Plays, Workflows and connectors execute through one governed path with independent verification.
- [ ] Interruption/correction prevents unauthorized writes, including race conditions.
- [ ] A real test-tenant learning cycle proves eligible, measured repeat-turn improvement.
- [ ] Full CI, frontend, backend, database, auth and production-safe smoke gates pass.
- [ ] Final redacted evidence report records passes, failures, blockers, remaining gaps and an explicit release decision.

**A passing test suite is necessary but insufficient. The release is complete only when the end-to-end product behaviour is demonstrated with appropriate live evidence and no release-blocking safety or reliability defects.**

---

## Additional mandatory workstream — Stripe Billing, MSP Wholesale, Metered Voice Usage and Compliance E2E

**Release gate:** This workstream is required for Phase 4 remediation, Phase 5 governed execution and Phase 6 production acceptance. It is a specification, **not evidence that billing or compliance controls already exist**. Do not enable live charges, customer-facing pricing changes, or production migrations without separate review and approval.

### Billing architecture and source-of-truth audit

- [ ] Inventory Stripe Products, Prices, subscription schedules, Checkout, Billing Portal, invoices, credits, coupons, promotion codes, taxes, trials, proration, dunning and payment methods; map each to backend handlers, frontend screens, database tables and tenant entitlements.
- [ ] Determine which entity is merchant of record for direct SMB subscriptions and for MSP-resold clients. Explicitly document whether the MSP is billed wholesale while independently billing its own clients, or whether Stripe Connect is required. **Do not assume Stripe Connect or a particular tax/merchant arrangement is already configured.**
- [ ] Use Stripe's subscription/invoice/payment records as the authoritative billing ledger and a reconciled internal entitlement projection for access. Define event ordering, retries, idempotency, backfills and failure reconciliation.
- [ ] Validate Stripe signature verification against raw webhook bodies; rotate secrets, constrain event types, prevent replay, deduplicate event IDs and recover from out-of-order delivery.
- [ ] Audit production/test mode separation, key custody, least-privilege API keys, price ID mappings, and feature flags.

### Subscription plans and entitlements

- [ ] Test new subscription via Checkout, paid activation, pending/failed payment, SCA/3DS, trial start/end, renewal, plan upgrade/downgrade, proration, cancellation at period end, immediate cancellation, reactivation and subscription pause (where supported).
- [ ] Test monthly and annual pricing, add-ons, promotional discounts, coupons, credit notes, refunds, taxes, invoice adjustments and failed-payment recovery. Assert the invoice and entitlement state after each transition.
- [ ] Enforce plan-level entitlements for seats, agents, workflows, Plays, connectors, usage allowances, concurrency and voice minutes without trusting frontend claims.
- [ ] Test grace periods and read-only/fail-closed behaviour during delinquency; never silently continue billable execution beyond approved caps.
- [ ] Verify changes made in the Stripe Billing Portal synchronize correctly and cannot cross tenant boundaries.

### Minute metering and usage reconciliation

- [ ] Define the billable unit precisely (for example, voice session connected seconds rounded according to the approved plan). Distinguish STT, TTS, real-time voice-to-voice, silence, paused sessions, retries and provider-reported usage; do **not** charge for text interactions as minutes unless the plan explicitly defines it.
- [ ] Specify whether minute allowances are pooled per organization, per client tenant or per seat, and how MSP wholesale allotments differ from retail client allotments.
- [ ] Instrument authoritative server-side session start/end, duration, model/provider, customer/tenant/MSP, correlation ID, unit, UTC event time, billing period and price version. Avoid PHI/PCI data in meter payloads.
- [ ] Emit each billable event once with a stable idempotency key; validate delayed events, partial sessions, disconnects, concurrent calls, time-zone boundaries, billing-period cutovers and usage corrections.
- [ ] Reconcile raw sessions → internal usage ledger → Stripe meter events/usage records → invoice line items → customer-facing dashboards. Test credits and disputes without modifying historical raw usage.
- [ ] Test included-minute depletion, thresholds, overage rates, hard caps, prepaid credits if applicable, notifications and administrative overrides with audit trails.
- [ ] Prove no double billing after webhook replay, worker retries, failed network requests or session reconnects; verify exact expected totals and currency precision.

### MSP wholesale and client billing

- [ ] Model MSP parent organization, reseller agreement, client sub-tenants, delegated administrators, direct customers and billing accounts as distinct identities.
- [ ] Define wholesale rate cards, markup/margin, minimum commitments, client-specific plan overrides, pooled versus dedicated minutes, invoice aggregation and wholesale discounts with effective dates and immutable price snapshots.
- [ ] Verify that MSPs can provision client tenants, assign plans, view permitted client consumption, manage delegated billing permissions and receive accurate consolidated wholesale invoices.
- [ ] Verify whether MSP client retail billing is external to Gravitree or explicitly implemented via approved Stripe accounts/Connect flows; never imply the platform collects funds on behalf of MSPs without verified implementation.
- [ ] Exercise client transfer between MSPs, suspension, cancellation, MSP termination and offboarding. Historical invoices and usage must remain correctly attributed; access must be revoked without deleting required financial records.
- [ ] Validate no cross-client visibility of prices, payment methods, invoices, discounts, usage, API keys, conversations, agents, Plays, Workflows, model context or connector credentials.

### Tenant isolation, governance and authorization

- [ ] Construct a permission matrix for platform owner, MSP owner/admin/billing admin/technician, client owner/admin/billing viewer, end user and service identity; apply least privilege at API, service, job and database levels.
- [ ] Test object-level authorization (BOLA/IDOR), organization and client scope, RLS, signed session claims, impersonation/delegation, cross-tenant search, exports, caches, background jobs and webhook processing.
- [ ] Assert that a client cannot alter its Stripe customer/subscription IDs, wholesale pricing, plan entitlements or usage ledger through request parameters.
- [ ] Require explicit approval for high-impact billing changes, rate-card modifications, refunds, credits and tenant reassignment; record actor, reason, before/after, timestamp and immutable audit reference.
- [ ] Enforce separation of duties for sensitive pricing and payout operations where required; test denied, expired and revoked permissions.
- [ ] Test secure webhook handling, SSRF/input validation, secrets redaction, encryption in transit/at rest, backup/restore and incident alerting.
- [ ] Integrate billing authorization with the existing canonical governance/write gate; voice commands must not bypass billing approvals.

### Compliance control mapping — SOC 2, HIPAA, PCI DSS and “AE2”

**These are compliance-readiness validation requirements, not a certification claim.** Applicable legal obligations and audit scope require review by qualified security/compliance counsel and independent assessors.

- [ ] **SOC 2:** map Security and any applicable Availability, Confidentiality, Processing Integrity and Privacy Trust Services Criteria to control owners and evidence: access reviews, change management, incident response, vendor risk, logging, backups, disaster recovery, vulnerability management, secure SDLC, encryption and periodic testing. A SOC 2 report requires an independent CPA examination; CI alone cannot certify it.
- [ ] **HIPAA (US):** first determine whether Gravitree handles electronic protected health information as a covered entity or business associate; if in scope, document BAAs (including applicable subprocessors), minimum necessary access, administrative/physical/technical safeguards, audit controls, breach procedures, retention and secure deletion. Test PHI exclusion from Stripe metadata, logs, analytics, voice traces and third-party providers unless explicitly authorized and contracted.
- [ ] **PCI DSS:** prefer Stripe-hosted Checkout/payment components and tokenization to minimize cardholder-data scope. Verify no PAN/CVV in Gravitree services, logs, databases, voice transcripts or analytics. Document applicable SAQ/scope, access controls, network/security testing, key management and Stripe shared-responsibility boundaries; using Stripe does not automatically establish PCI compliance.
- [ ] **“AE2” clarification required:** the requested term is not sufficiently specific to map responsibly to a standard. Confirm whether this means **SOC 2 Type II**, **AICPA AT-C Section 205 / SSAE 18**, or another framework before creating controls or claiming compliance. Track as an open requirements decision, not as a passed gate.
- [ ] Maintain a control-to-test-to-evidence matrix with owner, scope, applicability, last-tested date, exceptions, remediation and external auditor artifacts; redact sensitive customer and financial data.

### Required billing/security E2E scenario matrix

| ID | Scenario | Required observable result |
|---|---|---|
| BILL-01 | New direct SMB subscription and successful payment | Correct Stripe subscription, tenant entitlements, invoice and audit trail |
| BILL-02 | Failed payment / 3DS / retry / recovery | Correct state transitions; no premature paid entitlement |
| BILL-03 | Upgrade, downgrade, renewal and proration | Exact expected amounts, period and feature transitions |
| BILL-04 | Trial, coupon, promotional discount and expiration | Correct eligibility, price, invoice and expiry |
| BILL-05 | Cancel, refund, credit note and reactivation | Correct Stripe/internal reconciliation and permissions |
| BILL-06 | Voice minutes under allowance | Accurate server-side duration and remaining balance |
| BILL-07 | Overage, threshold, cap and billing-period boundary | Accurate rate and approved block/notification policy |
| BILL-08 | Concurrent calls, disconnect, replay and retry | No duplicate metering or double billing |
| BILL-09 | Usage ledger → Stripe → invoice → UI | Line-item totals reconcile with source events |
| BILL-10 | MSP wholesale provisioning and client retail mapping | Correct wholesale pricing, client attribution and approved reseller model |
| BILL-11 | MSP pooled versus dedicated minutes | Correct client usage isolation and parent allocation |
| BILL-12 | MSP invoice aggregation and discounts | Exact wholesale totals; no client leakage |
| BILL-13 | Client reassignment, offboarding and MSP suspension | Revoked access, correct financial attribution and preserved records |
| BILL-14 | Cross-tenant invoice/usage/price/API access attempts | Denied at API and database layers with audit evidence |
| BILL-15 | Billing role privilege escalation and delegated access | Least privilege and separation of duties enforced |
| BILL-16 | Webhook signature failure, replay and out-of-order delivery | Rejected/deduplicated/reconciled without corrupting state |
| BILL-17 | Voice-requested plan change or refund | Same approval and write gates as text; interruption prevents write |
| BILL-18 | PHI/PAN/CVV injection into conversation, logs and metadata | Sensitive data excluded/redacted; no unauthorized provider propagation |
| BILL-19 | Incident, backup/restore and audit evidence retrieval | Documented recovery, tamper-evident logs and control evidence |
| BILL-20 | Full MSP client journey | Provision → subscribe → use minutes → run governed Play/Workflow → invoice → reconcile → offboard |

### Test environments, implementation and release gates

1. Audit existing billing schemas, Stripe integration, metering workers, MSP models, permissions and compliance documentation **before** changing code. Identify duplicate systems and missing coverage.
2. Build deterministic contract/unit tests using Stripe fixtures and a fake clock; add isolated integration tests with Stripe test mode/test clocks and webhook fixtures.
3. Use disposable test tenants and separate MSP/client identities; verify both allowed and denied cross-tenant operations, including direct SQL/RLS checks where feasible.
4. Test real voice sessions for billable duration only after approved provider-cost limits and safe test accounts are configured. Separate simulated usage from actual provider minutes.
5. Run controlled E2E Play/Workflow and billing interactions through the canonical intelligence and authorization paths; record complete traces and independent readbacks.
6. Add CI gates for deterministic billing, security and tenant isolation; reserve live Stripe/provider tests for appropriately credentialed, isolated workflows. Never expose keys or customer data in CI artifacts.
7. Publish a reconciled billing evidence report, control coverage matrix, unresolved compliance scope decisions and a release decision. **No production charging changes without explicit approval.**

### Billing/security definition of done

- [ ] All BILL-01–BILL-20 scenarios have reproducible pass/fail evidence and exact financial assertions.
- [ ] Subscription and entitlement state reconciles with Stripe across all lifecycle transitions.
- [ ] Metered minutes reconcile across raw sessions, ledger, Stripe and invoices with zero unexplained duplicate charges.
- [ ] MSP wholesale and client boundaries are verified across UI, APIs, background jobs, data access and billing.
- [ ] Unauthorized billing mutations and cross-tenant access are blocked; voice and text share approval/write gates.
- [ ] SOC 2, HIPAA and PCI DSS applicability and controls are mapped with evidence; “AE2” is resolved as a requirement.
- [ ] No unresolved critical/high security or financial-integrity defects remain; audit evidence is redacted.
- [ ] Release owner signs off on test results, legal/compliance scope and any live-billing enablement.

**No compliance certification, audit opinion, HIPAA compliance, PCI validation or SOC 2 attestation may be claimed solely because these engineering tests pass.**
