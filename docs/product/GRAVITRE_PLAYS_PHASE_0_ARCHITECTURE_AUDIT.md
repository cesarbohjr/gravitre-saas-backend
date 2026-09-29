# Gravitre Plays / Outcomes — Phase 0 architecture discovery

Date: 2026-09-29
Branch: `feat/gravitre-plays-outcomes`
Base: unified `main` @ `6daa40762f93d1080513f0b12ce1730cc2ceb123`

This is the required audit-before-build step. It records what already exists and
what is missing so the Play program extends Gravitre without creating parallel
runtime, workflow, connector, governance, evidence, dashboard, or learning
systems.

## 1. Unified baseline

The 3.0 Plus frontend is now merged into `main`. The capability/governance
convergence is also on `main`.

Canonical capability seam:

- `GET /api/capabilities`
- `backend/app/routers/capabilities.py`
- `backend/app/capabilities/registry.py`

The registry composes canonical sources. It does not own a second connector,
ActionSpec, workflow, governance, event, metric, or verification catalog.

## 2. Architecture classification

| Area | Classification | Canonical implementation / notes |
|---|---|---|
| Agents | EXISTING | `operators`, agent identity records, agent APIs |
| Connectors | EXISTING | connector repository + connection-health semantics |
| Actions / tools | EXISTING | ActionSpec catalog + registered invoke handlers |
| READ / WRITE classification | EXISTING | catalog write authority |
| WRITE governance | EXISTING | `write_governance.resolve_write_user_approval`, HITL, PendingAction/HMAC paths |
| Workflows | EXISTING | canonical workflow definitions, runs, steps, schedules, execution engine |
| Conversation runtime | EXISTING | CognitiveTurnKernel / assistant chat path |
| Evidence stores | EXISTING / PARTIAL | audit, traces, workflow runs, task state, artifacts, verification metadata |
| Execution outcome | EXISTING | `ExecutionOutcomeEvent` / `finalize_execution_outcome` |
| Business outcome | PARTIAL | business-outcome projection and intelligence outcome events exist, but there is no Play-specific business-result contract/store |
| Metric definitions | EXISTING | org metric definitions + MQL/CAC/ARR platform defaults |
| Metric observations / measured values | MISSING | no general source-of-record metric observation store |
| Attribution | PARTIAL | correlational action-outcome coverage exists for a limited action set |
| Dashboard | EXISTING | current Dashboard/Measure surfaces and data hooks |
| Dashboard templates for Plays | MISSING | must extend existing dashboard rather than create another dashboard |
| Knowledge / Intelligence | EXISTING | RAG, knowledge graph, evidence/provenance, outcome learning |
| Play abstraction | MISSING | no canonical Play object/runtime found |
| Dataset provider abstraction | MISSING / NOT CRITICAL PATH | audit later; must not block initial Plays |

## 3. Canonical chain

The Play program must use this chain:

BUSINESS OUTCOME
→ PLAY
→ CANONICAL WORKFLOW
→ SIGNALS
→ CONTEXT
→ AGENTS
→ CONNECTORS / ACTIONS
→ GOVERNANCE
→ ACTION
→ VERIFICATION
→ BUSINESS OUTCOME
→ EVIDENCE
→ LEARNING
→ EXISTING DASHBOARD

A Play is an outcome-oriented layer over canonical workflows. It is not a
workflow runtime.

## 4. Existing capability registry

`tenant_capability_snapshot` already exposes the substrate required for Play
readiness:

- org agents;
- global catalog connectors;
- org connector status;
- ActionSpecs and READ/WRITE classification;
- runtime approval semantics;
- workflow primitives;
- event taxonomy;
- metric definitions;
- write-verification modes;
- evidence-source mapping.

The snapshot correctly reports Play schema and dashboard templates as
unavailable today. That remains truthful until implemented.

## 5. Existing outcome architecture

There are three different concepts that must stay distinct.

### Execution outcome

`backend/app/services/execution_outcome.py`

Purpose: terminal execution state and fanout.

Examples:

- completed;
- failed;
- cancelled;
- partial_success;
- flagged_for_review.

This answers: **did the execution finish and what verified execution output was
produced?**

It does not by itself prove a business result.

### Learning / intelligence outcome events

`intelligence_outcome_events`

Purpose: learning/event substrate for workflow, prediction, agent and connector
outcome signals.

This can carry before/after values and measured state, but it is not currently
a complete Play business-outcome ledger.

### Business-outcome projection

Existing business-outcome projection distinguishes evidence strength including
verified, accepted-unproven and unverified execution results.

This must be reused as input/evidence. It must not be silently re-labelled as
verified business impact.

## 6. Required business-result gap

The missing concept is a small, explicit business-result contract that can tie:

- org;
- Play;
- canonical workflow/run;
- affected entity;
- metric/outcome type;
- baseline;
- result;
- delta;
- unit/currency;
- attribution method/weight;
- source systems/records;
- evidence;
- agents/actions;
- verification method;
- verification state;
- occurred/recorded timestamps.

No schema is added in Phase 0. Phase 0 only establishes that this gap is real
and distinct from execution status.

## 7. Evidence rule

The Play program must keep these states separate:

1. SIGNAL
2. CONTEXT
3. RECOMMENDATION
4. ACTION
5. VERIFICATION
6. OUTCOME

Provider acceptance is ACTION evidence. It is not VERIFIED SUCCESS unless an
independent verification mechanism supports the result.

Existing write-verification modes therefore matter directly to Play maturity.

## 8. Initial Play readiness

### Revenue Recovery

Current architecture is closest to a truthful end-to-end result loop.

Available substrate:

- Stripe / QuickBooks reads;
- some source-of-record re-read verification;
- correlational business-impact coverage for selected revenue actions;
- canonical approval governance.

Missing/partial:

- failed-payment / stalled-revenue signal detector;
- general business-result event contract;
- verified recovered-revenue calculation.

### Customer Rescue

Available substrate:

- support/CRM reads;
- churn advisory signal path;
- governed CRM/support writes.

Missing/partial:

- reliable churn-risk signal depends on sufficient labeled data;
- retained-revenue / churn-avoided verification;
- business-result event contract.

### Marketing Performance

Available substrate:

- ad / analytics / CRM connector reads;
- MQL and CAC definitions;
- dashboard/intelligence surfaces.

Missing/partial:

- spend-to-pipeline anomaly signal;
- complete source-of-record attribution;
- business-result event contract.

## 9. First implementation decision

The first implementation slice will be **Play contract + readiness**, not Play
execution.

It will:

- define a Play as a reference to canonical workflow(s), required signals,
  connector/action dependencies, verification requirements and outcome metrics;
- resolve readiness from `GET /api/capabilities` / the underlying registry;
- support the maturity vocabulary OBSERVE / RECOMMEND / ACT WITH APPROVAL /
  ACT WITHIN POLICY;
- contain no new workflow executor;
- contain no new connector/action catalog;
- contain no new approval engine;
- make no revenue-impact claim.

Revenue Recovery remains the first candidate for live implementation after the
contract/readiness layer because it currently has the strongest verification
substrate.

## 10. Open architecture decisions before persistence

These remain deliberately open until the next audit slice:

1. Whether a business `OutcomeEvent` should persist in a new narrow table or
   extend an existing tenant-scoped outcome store without overloading execution
   semantics.
2. Whether measured KPI snapshots require a separate `MetricObservation`
   record or can be source-projected for the first Plays.
3. Whether Play definitions should persist as first-class tenant records or
   begin as versioned platform templates instantiated into canonical workflows.

No decision may create a second workflow runtime or a generic analytics
warehouse.

## Phase 0 result

PHASE_0_ARCHITECTURE_DISCOVERY = COMPLETE

Next:

1. audit Model Studio / dataset architecture;
2. audit exact Play persistence/reference options;
3. audit OutcomeEvent persistence options;
4. then implement the smallest canonical contracts.
