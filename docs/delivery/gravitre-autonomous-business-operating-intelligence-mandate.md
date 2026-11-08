# Gravitre — Autonomous Business Operating Intelligence & Execution Mandate

**Owner:** PR #611 full-ecosystem remediation and implementation. **Voice contract owner:** PR #610. **Status:** DESIGN DECISION / ENGINEERING GATES NOT YET CERTIFIED. **Decision:** The 43-finding audit is a floor, not the final product specification. No change to merge/deploy authorization. No autonomous unapproved provider writes.

## 1. North-star outcome
For any legitimate business goal expressed in ordinary language (e.g. "I need to increase sales"), Gravitre shall **understand the business objective, inspect authorized business context, expose evidence-backed gaps and opportunities, form prioritized hypotheses, model scenarios and confidence, assemble appropriate existing and/or generated agents/Plays/workflows on the visual canvas, seek consent for material external actions, execute and monitor durable tasks, independently verify provider outcomes, measure business KPIs, and adapt the plan**.

The user owns intent, constraints, budget, risk appetite and approvals. Gravitre owns discovery, decomposition, execution architecture, coordination and follow-through. A missing connector or insufficient evidence must produce an honest partial diagnosis and a minimal precise request; never fake a diagnosis, integration or completion.

**Operating modes:** (a) answer/explain, (b) diagnose/recommend, (c) plan/simulate, (d) execute with governance, (e) recurring monitor/optimize. All modalities use the **same** tenant-scoped authority, task graph and source-of-truth. Voice is a surface, not a second business brain.

## 2. Executable reference journey — "increase sales"
1. Parse "increase sales" into an objective with tentative KPI (qualified pipeline/booked revenue), timeframe and constraints inferred only from authorized tenant records; make assumptions visible, ask at most necessary clarification.
2. Inventory actual connector readiness and scopes for CRM, marketing, website analytics, finance/commerce and sales tools; no tool-name hallucinations. Map missing sources and confidence.
3. Retrieve current vs prior-period funnel: leads by channel, MQL/SQL, meeting-to-opportunity, opportunity-to-close, average deal value, velocity, retention, customer acquisition cost, spend, capacity, cohort effects. Preserve source, timestamps, unit definitions and tenant.
4. Separate **observations** (e.g., stage conversion dropped) from **hypotheses** (e.g., response delay causing loss); calculate effect size, baselines and uncertainty, and identify cost/risk of inaction.
5. Generate 2–4 plausible interventions: lead response SLA, conversion optimization, nurture/re-engagement, offer/positioning, pipeline hygiene; score by impact, evidence/confidence, implementation effort, cost, reversibility and time-to-value. Include no-action baseline.
6. Compile the chosen interventions into a typed, versioned executable DAG using registered agent capabilities, existing reusable Plays and workflows first, generated canvas nodes only when necessary; validate every node against actual tool schema, organization scope, connector state and action policy. Preview the graph in the canvas, with inputs, owners, checkpoints and expected artifacts.
7. Simulate expected KPI deltas as ranges/scenarios with assumptions, sensitivity and calibration history; no invented lift or guaranteed revenue.
8. Execute allowed **read-only** research and internal reversible preparation under approved standing policy; pause for explicitly governed spending, messaging, CRM writes, publication, deletes, sensitive disclosure or external side effects. Each approved action gets an idempotency key and durable state.
9. Independently read back external writes; persist evidence and fan out exact terminal outcome to the conversation, canvas, task status and downstream consumers. Resume safely after cancellation, restart or partial failure.
10. Monitor metrics with attribution limits, detect drift and propose or safely apply policy-approved plan adjustments. Escalate when a plan no longer fits constraints or when signals are too weak.

**Definition of success:** an authorized, evidence-backed plan becomes an inspectable run, not merely prose; approved tasks are actually performed and verified; baseline and follow-up metrics are reported, with uncertainty. Business outcome improvement is measured over an appropriate window, not asserted from synthetic QA.

## 3. Cross-department coverage contract
The same goal lifecycle must apply to:
- Sales / revenue: pipeline, conversion, forecasts, account prioritization, outreach approvals.
- Marketing / growth: attribution, CAC, campaigns, SEO, conversion, brand demand.
- Finance: cash runway, expenses, receivables, margin, scenario planning, anomaly review (no unapproved payments).
- Customer success / support: churn signals, service coverage, case resolution, renewal risk.
- Operations / supply chain: SLA, bottlenecks, capacity, procurement, inventory and risk.
- People / HR: staffing forecasts, onboarding, process capacity; privacy/HR authorization boundaries.
- Product / engineering / IT: adoption, defects, incidents, roadmap tradeoffs, service reliability and security.
- Leadership / strategy: goals, portfolio prioritization, multi-department dependencies and executive reporting.

Every domain must declare: minimum viable connected evidence, metric semantic definitions, capability registry, read/write permissions, Play templates, failure modes, synthetic golden goals and a domain-specific acceptance scorecard. **Do not claim universal coverage when a department is only a prompt template**. Add domains in certified vertical slices with shared infrastructure.

## 4. Engineering architecture — required additions
### A. Goal-to-plan compiler (new)
Typed GoalSpec: intent, business entity/tenant, objective metric, horizon, constraints, source provenance, confidence, decision ambiguity, authorized effects. PlanSpec: ranked strategies, assumption graph, KPI target, typed DAG, candidate agent/Play/workflow IDs and capability/connector requirements. Validate compile-time compatibility and runtime capability availability. Preserve goal->plan->run IDs and versions. Support plan amendment, diffs, rollback and explainable "why this action".

### B. Business semantic and evidence layer (new or consolidate existing)
BusinessEntity/MetricSpec registry with metric definitions, timestamps, lineage, source-of-record, dimensional filters and tenant isolation. Normalize CRM/Ads/Analytics/finance semantics without pretending missing fields exist. Evidence freshness windows, conflict detection, bounded incremental sync, connector health and event-driven change capture where available. Explicit UNKNOWN for unsupported inference.

### C. Opportunity/risk detection and recommendation ranking (new)
Rule and statistical detectors before expensive model passes; business baselines, seasonality and anomaly tests, unit economics, opportunity hypotheses and recommendation ranking. Evidence-backed reason/counterexample, potential upside/downside, cost, confidence, constraints and required approvals. No unsupported causal claims.

### D. Forecasting/scenario engine (new)
Pluggable baseline forecasts per metric and data volume: deterministic arithmetic, trend/seasonality, probabilistic intervals and backtesting; no model selection by marketing label. Monitor WAPE/MAE/calibration and drift, evaluate out-of-sample accuracy, expose unknown/insufficient history. Scenario sensitivity separates hypothetical interventions from learned causal effects.

### E. Agent/Play/workflow execution unification (extend existing)
One governed compiler and execution state model across agents, reusable Plays, workflow canvas, approval/cancellation/revocation, async jobs and tools. Reuse actual registries and dispatchers; no parallel shadow executor. Typed node I/O, bounded fanout, dependency checks, cycle prevention, cost estimates, timeout and failure compensation. Generated canvas edits must round-trip to executable graph and back, with stable node IDs, statuses and a meaningful diff.

### F. Continuous goal operator (new; policy opt-in)
Goal lifecycle PROPOSED -> DIAGNOSING -> PLAN_READY -> WAITING_APPROVAL -> RUNNING -> MONITORING -> COMPLETE/PAUSED/FAILED. Event-driven / scheduled evaluation (rate bounded), opportunity score updates, stop-loss budgets, stale-data pause, source change alerts, plan recalibration, user digest. No independent agent authority to issue new material external writes.

### G. Latency, efficiency and quality control (cross-cutting)
Instrument p50/p95 per route and stage (input->context->routing->plan->tool->provider->outbox->UI), token and provider spend, cache hit/miss, queue time and voice first audible sample. Parallelize independent reads; cache with tenant-safe invalidation and freshness contracts; prefer incremental aggregates, semantic indexing with provenance, tiered model selection, streaming plans and long-task progress that corresponds to real work. Establish baseline and regression SLO before tuning. Correctness and governance outrank artificial speed.

### H. Observability, autonomy evaluation and cost governance (new/extend)
Trace goal->reasoning evidence->plan versions->run steps->provider outcomes->business metrics with redacted event IDs, privacy retention and consent. Evaluation corpus of underspecified user goals, adversarial instructions, missing connectors, conflicting data, inactive Plays, denied writes, cancellation, retries, dead workers and cross-tenant attacks. Track factual grounding, completion, quality of generated DAG, critical clarifications, unauthorized writes (zero tolerance), latency, total cost per goal and long-horizon usefulness. Runtime policy enforces per-goal spending and rate limits.

## 5. Plan-first evidence gates
**G0 Inventory**: deployed topology and true active entrypoints, 43 findings, capability and metric coverage, 92 Actions workflows, agent/Play/workflow inventories, per-domain mapping.
**G1 Goal understanding**: underspecified real-world objective set across all domains, correct GoalSpec and minimal clarification, grounded assumptions.
**G2 Diagnose**: connector health/authorization, lineage/metric consistency, findings and uncertainty with actual readback, negative cases.
**G3 Compose**: valid PlanSpec->DAG/canvas round-trip, reusable first, schema-aware nodes, executable compiled graph, policy/cost preview, no nonexistent capability.
**G4 Governed execute**: approval gates, tool scope/tenant guards, durable checkpoint, provider readback, idempotent replay, cancellation and worker crash recovery; no unauthorized external effects.
**G5 Predict**: out-of-sample accuracy/calibration and honest scenario bounds; insufficient-data abstention.
**G6 Continual optimization**: scheduled/event-driven goal monitoring, feedback and drift policies, safe replan and human override.
**G7 Experience**: web+voice semantic parity, natural turn-taking, mobile/desktop, truthful progress, user-facing canvas, latency and acoustic quality from PR #610.
**G8 Release**: exact-head CI, actual downstream integrations, safe production acceptance, cost budget, rollback and sign-off. Per-finding 43-ledger stays open until its own evidence is complete.

For every gate publish executable tests, scenario digest, exact SHA and environment, synthetic vs live designation, skipped/blocked counts, evidence links, owning PR, severity and decision. **Not-run is never pass.** Gate results never substitute for actual business outcome measurement.

## 6. Dependency-aware program sequence (PR #611 unless noted)
- **Phase 0 — diagnosis / correctness:** finish source->runtime audit and 43 finding classification; prioritize P0 security/tenant/runtime and existing connector/plan functionality. Link defects to executable tests and exact release blockers.
- **Phase 1 — unified business brain:** metric semantics + context provenance + GoalSpec + evidence retrieval + objective/intent authority. Red/green regression for vague goals and missing evidence.
- **Phase 2 — plan/Play/canvas compiler:** capability contract, registered skill discovery, typed DAG validation, reuse and generation, canvas round-trip and previews. No unverified auto-launch.
- **Phase 3 — governed action engine:** persistent orchestration, approvals, connector readiness, provider readback, crash/replay, trace and cancellation. Reuse existing working components; remove duplicate owners only after demonstrated parity.
- **Phase 4 — predictive and proactive:** opportunity/risk scoring, calibrated forecasts, scenario model, opt-in monitors, drift-triggered recommendations and budget guard.
- **Phase 5 — integrated cross-domain acceptance:** six to eight goal journeys across every declared department; varied connector coverage, no-data path, unsupported action path; voice V0–V7 owned by #610, QA30 evidence ingested into #611.
- **Phase 6 — operational release:** 92-workflow audit, measured p50/p95, load/cost profile, exact-head certification, controlled production and rollback, required independent real-world acceptance; no global merge/release while blocking proofs absent.

Work on safe independent vertical slices concurrently, but do not mark complete until downstream source-of-truth proof. Existing portal 343328749 can support one explicitly authorized QA contact test; no extra paid Railway staging or test portal needed.

## 7. Product acceptance — multi-goal benchmark
For "increase sales", "reduce customer churn", "improve cash flow", "why are support tickets escalating?", "reduce operating costs", "we need better hiring", "fix slow customer onboarding", and "reduce production incidents", require:
- Goal understood without a product configuration questionnaire.
- Actual available data diagnosed (or explicitly stated gaps), quantitative observations separated from hypotheses.
- Correct agents, reusable Plays and workflows selected and valid editable canvas generated.
- Ranked actions with business outcomes, uncertainty, cost/risk and approval boundaries.
- At least one authorized multi-hop journey executed, independently verified, persisted and reflected consistently across UI and chat.
- Proven no-write path for denial/revocation/missing scope; recovery for duplicate callback/process crash.
- Evaluation against defined accuracy, cost, latency and usefulness budgets, with human acceptance for real-world quality.

## 8. Non-negotiable decisions
1. No chatbot-only interpretation of success; **intent-to-verified-action is the product**.
2. No universal "autonomous" marketing claim until supported, audited domain coverage is real.
3. No divergent agent/Play/workflow engines or disconnected decorative canvas.
4. No fabricated forecasts, causal effects, tool activity, provider results or completion.
5. No unapproved external campaigns, messaging, payments, contact edits, destructive operations or data sharing.
6. Existing systems are reused when they meet contracts; remove/rewrite only after real active-caller proof, migration and rollback.
7. PR #611 remains unmerged and not production certified until its remediation release policy is met. PR #610 owns functional voice fixes; PR #611 owns cross-system acceptance.
