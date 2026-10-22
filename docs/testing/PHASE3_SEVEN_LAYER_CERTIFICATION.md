# Phase 3 — Seven-Layer Integration Certification

Status: **test specification only; NOT certified**. This document is an acceptance contract, not proof of passing tests.

## Scope
Seven canonical intelligence capabilities from `backend/app/services/intelligence_router.py`: contextual, sentiment, causal, temporal, relational, adaptive, predictive.

Eight execution surfaces: Flows, Plays, agents, workflows, connectors, knowledge fabric, memory, governance/approvals. Baseline matrix: **7 × 8 = 56** capability/surface intersections. Each cell must link to a reproducible automated test, fixture, observed behavior, and CI artifact. A registered route, API 200, or catalog inventory does not count as certification.

## First three integrated scenarios
1. **Customer support / Customer Rescue:** frustrated customer with recurring incidents; evidence retrieval, sentiment and temporal context, causal uncertainty, relationship analysis, escalation forecast, agent handoff, approval and source-of-record verification.
2. **Sales / Revenue Recovery:** stale CRM opportunity, conflicting account history, predicted risk, agent recommendation, explicit approval for CRM mutation, deduplication and readback.
3. **IT incident management:** correlated alerts, topology relationships, incident chronology, probable cause vs hypothesis, predictive impact, adaptive recommendation, governed remediation and readback.

For each scenario require baseline vs intelligence-enabled differential assertions: decisions must change when relevant evidence changes; missing evidence must produce uncertainty, not invented certainty.

## Adversarial fixtures
- Contradictory or stale knowledge and memory.
- Missing/unavailable intelligence enrichment: optional advice may degrade, but authorization and consequential writes must fail closed.
- Connector timeouts, retries, duplicate events, and idempotency.
- Spoken `yes… wait`, transcript correction, interruption, and canceled turn before final provider commit.
- Concurrent agents, conversation-state revision conflicts, stale cancellation tokens, and competing approvals.
- Cross-tenant data attempts and malicious instructions inside retrieved context.
- Provider accepted action versus independently verified business outcome; never conflate them.

## Required evidence and gates
For every test record: commit SHA, deterministic seed, scenario ID, capability, surface, observed decision, expected decision, write attempts, writes committed, approval state, independent readback where authorized, and artifact link. Do not log secrets or customer content.

**P0 blockers:** any unauthorized or premature write, tenant leakage, bypassed approval, false verified outcome, or replay instability. Require 20/20 deterministic `yes… wait` trials and no unsafe writes; retain existing voice replay regression. Report all other failures explicitly rather than marking partial coverage green.

**P1 requirements:** decision correctness, provenance, handoff continuity, latency budget, fallback semantics, and learning updates from verified outcomes.

## Implementation sequence
1. Create a machine-readable 56-cell manifest and identify real call sites/tests; mark absent coverage as NOT TESTED.
2. Add deterministic offline scenarios and CI artifacts, including a safety-blocking job.
3. Add differential and concurrency tests against production-equivalent final write gates.
4. Add authorized provider-backed acceptance with independent readback, separately from offline CI.
5. Expand to the full Plays catalog; inventory is not end-to-end certification.

Do not merge or deploy on the strength of this document alone.
