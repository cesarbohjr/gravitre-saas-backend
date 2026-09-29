# Phase -1 findings and Plays program sequencing (accepted 2026-09-28)

Phase -1 (product convergence + capability contract) is accepted. It precedes the
GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM, whose Phases 0–17
remain authoritative. The -1J priority list does not replace the Master Program.

Master Program text: not present in this repository or in available agent
transcripts as of 2026-09-28. It must be supplied before Phase 0 starts.

Full contract (inventories, matrix, readiness): `docs/platform-reconciliation/gravitre-product-contract.md`
in local-only commit `573c249a` on `main` (not pushed; see "Core handoff").

## Recorded findings (do not overstate)

- Plays do not exist as a canonical product abstraction.
- Goal progress has no canonical backend source. The UI shows "Not measured" unless the goal is completed.
- Stored business metric values do not exist. Metric definitions exist (`org_metric_definitions`, platform MQL/CAC/ARR), but definitions are not measured values.
- Agents, assignments and evidence are partially wired.
- Some frontend routes still derive or fill state themselves (`/api/agents` BFFs, assignment steps, Connectors shipped list, builder council fallbacks).
- The capability registry (local run) covers 85 vendors, 731 actions and 362 WRITE actions.
- 283 WRITE actions have provider-acceptance evidence only (`accepted_async`) and no independent post-action verification.
- No initial Play (Customer Rescue, Revenue Recovery, Marketing Performance) is LIVE_READY.
- External organization connection readiness has not been evaluated; readiness was computed without org context.

## Contract rules carried into the Plays program

1. **Capability registry.** The frontend consumes it only through a canonical authenticated, tenant-scoped, read-only API (conceptually `GET /api/capabilities`). No TypeScript copy of the registry, no second action catalog, no Play-specific connector/action catalog.
2. **Autonomy is blocking.** "No approval policies" appearing to auto-run writes must be reconciled against the governed-WRITE runtime by core. The frontend displays recorded, runtime-derived policy only, and must not present "Act within policy" as available unless the runtime proves the action may auto-run.
3. **Outcomes.** No generic KPI/metric-value table first. Model: workflow/action → observable result → verification → OutcomeEvent → aggregation → dashboard. Dashboard KPIs aggregate from verified OutcomeEvents, canonical execution data and real system-of-record values. A separate metric store is added only for a use case those cannot represent (Master Program Phases 3–4 audit first).
4. **Provider acceptance ≠ business verification.** `accepted_async` supports ACTIONED, never VERIFIED SUCCESS. Verification requires a re-read, downstream state, a webhook/event, an independently observed source record, explicit human verification, or another canonical mechanism.
5. **Maturity model (one implementation per Play).** OBSERVE → RECOMMEND → ACT WITH APPROVAL → ACT WITHIN POLICY → VERIFY → OUTCOME. Availability depends on connected systems, ActionSpecs, data availability, agent permissions, canonical approval policy and verification capability.
6. **First-result experience.** Useful in OBSERVE/RECOMMEND without WRITE access. Show honest readiness / insufficient-data states; never promise signals when data is absent.

## Sequence

1. Converge `feat/gravitre-3.0-plus-frontend` with latest `main`, re-verify, owner-live Preview.
2. OWNER_LIVE_ACCEPTANCE on real surfaces and canonical state; fix contract defects it exposes.
3. Merge 3.0 Plus into `main` by the approved process.
4. New branch from unified `main`: `feat/gravitre-plays-outcomes`. `feat/gravitre-3.0-plus-frontend` never becomes the Plays branch, and no Play or Outcome tables are built on it.
5. Critical path: Phase 0 repo audit → Phase 2 Play architecture audit → Phase 3 Outcome audit → Phase 4 Outcome contract (if required) → Phase 5 evidence/verification wiring → capability-registry consumption → Customer Rescue → Revenue Recovery → Marketing Performance → dashboard template infrastructure → Play dashboard templates → live Play verification → dataset / Model Studio providers. Phase 1 (dataset architecture audit) may run early; Hugging Face must not block the first live Play.

## Core handoff (core agent owns)

- **Capability API seam.** Build the authenticated, org-scoped, read-only capability route over the registry in local commit `573c249a` (`backend/app/capabilities/registry.py`, 12 tests). Do not duplicate it; the frontend will consume the route once it exists.
- **Autonomy rule.** Prove the canonical rule for writes when an org has no `hitl_policies`, and where `trust_level` is enforced (today: ReAct write gate and voice PSTN, not `invoke_tool`).
- **Chat panel copy (protected seam).** `components/gravitre/assistant/chat-execution-panel.tsx` states "write steps run automatically unless your approval settings require confirmation." It predates this branch and asserts the unreconciled rule; core should correct it when the rule is proven.
