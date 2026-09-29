# Gravitre Plays / Outcomes — implementation sequence status

Date: 2026-09-29
Branch: `feat/gravitre-plays-outcomes`

This document is a progress ledger, not a replacement for the Master Program.

## Completed in this branch

### Phase 0 — architecture discovery

COMPLETE.

Canonical agents, connectors, actions, workflows, governance, evidence,
learning, BusinessOutcome and Dashboard were audited before implementation.

### Phase 1 — Model Studio / dataset audit

COMPLETE.

Existing training datasets/jobs/model registry are retained. No external
dataset provider has been added.

### Phase 2 — Play architecture

IMPLEMENTED FOUNDATION.

A Play is a non-executable outcome contract referencing canonical workflows and
canonical capability dependencies.

### Phase 3 — outcome audit

COMPLETE.

Execution outcome, BusinessOutcome projection, learning events and business
results remain separate concepts.

### Phase 4 — business result contract

IMPLEMENTED FOUNDATION.

Typed Play business results reuse `intelligence_outcome_events`; no second
generic outcome store was created.

### Phase 5 — evidence drill-down

IMPLEMENTED FOUNDATION.

A business result can drill through metric/entity → Play → canonical workflow
run → agent/action → approval → source records/evidence → verification.

Source-of-record verification now appends a new verified business-result event
from an existing org-scoped ACTIONED event. The ACTIONED event is preserved for
audit lineage; provider acceptance is never rewritten into business success.

### Phase 6 — first three Plays

IMPLEMENTED OBSERVE / RECOMMEND FOUNDATION.

- Customer Rescue
- Revenue Recovery
- Marketing Performance

All three reuse existing signal/evidence systems. None fabricates business
impact.

### Phase 7 — execution chain

IMPLEMENTED FOUNDATION.

Plays can bind to canonical workflows. Optional `playKey` is threaded through
the existing `POST /api/workflows/execute` path only after exact binding
validation. Existing workflow policy/approval/runtime remains authoritative.

Terminal Play-bound writes can record `ACTIONED` in the Play business-result
ledger. They cannot auto-promote to `VERIFIED SUCCESS`.

### Phase 8–11 — Dashboard audit / templates / truthful outputs / custom view

IMPLEMENTED FOUNDATION.

The existing Dashboard now shows Play readiness and includes outcome-oriented
presets:

- Executive Overview
- Customer Rescue
- Revenue Recovery
- Marketing Performance

Existing customization remains the Custom path.

No separate dashboard product was created and unverified impact metrics remain
absent.

### Phase 12 — dataset purpose relationships

IMPLEMENTED FOUNDATION.

Existing training datasets now have a narrow purpose-binding layer supporting:

REFERENCE, BENCHMARK, RUNTIME RETRIEVAL, RAG, EVALUATION, TESTING,
FINE-TUNING, TRAINING, SYNTHETIC, AGENT BENCHMARKING

and targets:

agent, model, department, evaluation, Play, workflow.

This does not add an external dataset provider.

## Explicitly not started

### Phase 13 — external dataset provider

NOT STARTED.

Hugging Face or another provider remains deferred until the first Plays have
live proof. No provider-specific special case has been introduced.

## Governance state

- tenant scope enforced in Play read models and migrations;
- workflow binding mutation requires admin;
- binding/unbinding audited;
- Play observe APIs do not execute actions;
- ACT WITHIN POLICY remains fail-closed;
- workflow execution still uses canonical policy/approval logic;
- execution success remains distinct from business success;
- verified business success requires verification evidence.

## CI note

Exact-head CI at `9b2f95bcaacf31c78b7d2445882dbc45eba896c5`
completed successfully before the source-verification extension.

The current head must pass a fresh exact-head run before merge.

## Next sequence

1. fresh exact-head CI after source-verification + router contract tests;
2. deployed API proof for Play readiness + observe routes;
3. prove one canonical Play workflow binding in a non-destructive environment;
4. prove ACTIONED evidence linkage against that bound workflow;
5. prove a real source-of-record verification event before any VERIFIED SUCCESS;
6. then begin provider-neutral external dataset-source work; provider-specific
   Hugging Face integration remains after the abstraction is proven.
