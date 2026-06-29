# Ground-truth outcome measurement roadmap (STA-289)

**Status:** Roadmap / deferred — estimate labeling shipped (STA-286)  
**Date:** 2026-06-21  
**Related:** `docs/ai/OUTCOME_ESTIMATE_LABELING.md`, `apps/web/lib/outcome-labels.ts`

## Problem

Gravitre today exposes:

- **Estimates** — catalog hours saved, ROI heuristics (publisher metadata)  
- **Operational counts** — tasks completed, workflow success rate from product telemetry  

Neither proves **business outcome** (hours actually saved, revenue impact, quality delta) without ground-truth measurement against customer systems or controlled studies.

STA-286 fixed the **labeling** gap ("Estimate" vs "Operational"). STA-289 defines the **measurement** path — intentionally deferred until core execution and connector demos are stable.

## Phases

### Phase A — Instrumentation (Q3 2026)

- [ ] Standard event schema: `outcome.measurement.eligible` when a workflow completes with tagged business intent  
- [ ] Link runs to marketplace asset / dept pack provenance IDs  
- [ ] Export API: anonymized run outcomes for pilot analysis (internal only)

### Phase B — Connector-attributed deltas (Q4 2026)

- [ ] Before/after snapshots for **read-only** CRM fields (deal stage timing, ticket resolution timestamps)  
- [ ] Compare pre/post windows per org with explicit **Measured** badge when sample size thresholds met  
- [ ] Exclude financial/HRIS writes from auto-measurement (compliance)

### Phase C — Customer-confirmed outcomes (2027)

- [ ] Optional pilot survey / Slack interactive confirmation ("Did this save time?")  
- [ ] Tie confirmed responses to run IDs; store as `outcome_confirmations` table  
- [ ] Marketplace ROI dashboard third tier: **Confirmed** (alongside Estimate and Operational)

### Phase D — Controlled studies (enterprise)

- [ ] Export pack for customer BI (Snowflake/BigQuery) with run + connector audit join  
- [ ] Partner SOW template for time-on-task studies  
- [ ] SOC2 evidence linkage for outcome claims in sales

## Non-goals (this roadmap)

- Replacing customer HRIS/payroll as source of truth for headcount savings  
- Presenting LLM-generated "impact scores" as measured ROI  
- Auto-publishing marketplace hours-saved without Estimate badge until Phase C

## Success criteria

1. Any UI surface showing "hours saved" without Estimate badge must cite a ground-truth source ID.  
2. Pilot org can export run-linked measurement report.  
3. Product marketing Strict policy (STA-261) allows "measured" copy only for Phase B+ features with sample disclosure.

## Dependencies

- STA-284 execution audit completeness  
- STA-274 audit log integrity (measurement requires trustworthy event stream)  
- STA-285 demo-safe simulation (pilots must not conflate simulated and live outcomes)

## Immediate action (done)

- Estimate labeling shipped — see STA-286 doc  
- This roadmap ticket closes the **planning** deliverable; implementation remains future work tracked under new tickets when Phase A starts
