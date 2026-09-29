# Phase -1 findings and Plays program sequencing (accepted 2026-09-28)

Phase -1 (product convergence + capability contract) is accepted. It precedes the
GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM, whose Phases 0–17
remain authoritative. The -1J priority list does not replace the Master Program.

Master Program record: `docs/product/GRAVITRE_PLAYS_OUTCOMES_DATASETS_DASHBOARD_MASTER_PROGRAM.md`
(Phase -1 addendum, acceptance and owner-live gate stored verbatim; the Phases 0–17 body is not yet
recorded because its text is not present in the repository or available transcripts).

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

## Public docs and marketing claims (separate from Plays; classified 2026-09-28)

Correction: the Phase -1 contract said public docs cite a "removed" `/api/operator/*` API. That was wrong.
`backend/app/operator_module/router.py` (prefix `/api/operator`) is mounted in `backend/app/main.py:684`
and serves `context/{run,workflow,connector,source}/{id}`, `prompts` and `action-plan`.

| Item | Classification | Evidence | Action |
|---|---|---|---|
| `/api/operator/*` paths in `runs.mdx`, `connectors.mdx`, `ai-operator.mdx`, `api/quickstart.mdx`, `concepts/platform-overview.mdx` | VERIFIED_CORRECT (code) | router mounted, `main.py:684` | none |
| Action-plan request bodies in `api/quickstart.mdx` (camelCase) and `ai-operator.mdx` (`instruction`, `environmentId`) | STALE | `ActionPlanRequest` = `primary_context` / `related_contexts` / `operator_goal`, no aliases (`operator_module/schemas.py:158`) | fixed to the schema |
| Execute body `"workflowId"` in `api/quickstart.mdx` | STALE | `ExecuteRequest.workflow_id`, no alias (`routers/workflows.py:143`); Next route is a pure proxy | fixed to `workflow_id` |
| Marketing API page action-plan path `/api/operators/{id}/action-plans` (introduced in `39ec95d5`) | STALE (regression) | `/api/operator/action-plan` is the endpoint matching "Generate an AI action plan from natural language" | reverted to `/api/operator/action-plan` |
| Marketing API page workflow paths `/api/workflows/execute`, `/dry-run`, `/runs/{id}/approve` (`39ec95d5`) | VERIFIED_CORRECT (code) | `routers/workflows.py:1028, 1686, 2729`; the previous `{id}` variants do not exist | none |
| `npm install @gravitre/sdk` | STALE | npm registry 404 (2026-09-28) | removed |
| `pip install gravitre` | STALE | PyPI: no matching distribution (2026-09-28) | removed |
| `go get github.com/gravitre/go-sdk` | STALE | GitHub repository 404 (2026-09-28) | removed |
| Marketing API page `@gravitre/sdk` code sample | STALE | package not published | replaced with a `curl` call to `/api/workflows/execute` |
| Changelog 2.1.3 "Official Node.js SDK" / "Official Python SDK" | STALE | same registries; docs FAQ and quickstart already say "No official SDK yet" | SDK claims removed from the entry |
| FAQ "Is there an official SDK? Not yet." and quickstart "No official SDK yet" callout | VERIFIED_CORRECT | registries above | none |
| API key auth (`Authorization: Bearer YOUR_API_KEY`) in public docs, "OAuth 2.0, API keys, and signed webhooks" feature line | UNVERIFIED | not checked in this pass | none — needs a separate check |

Code-level only; no production HTTP call was made against these endpoints.

## Billing E2E classification (CI run 36505964385, SHA `efc0c988`)

INCONCLUSIVE_TIMEOUT with a known failing spec. The job hit its 20-minute `timeout-minutes` while running
`Run billing Playwright suite` after 77 of 220 tests (63 distinct passed). Before the cutoff, one test failed at
every width (with retry):

- `e2e/creative-pilot3-knowledge-fabric-widths.spec.ts` — "technology entity convergence mounts @ {390…1440}".
  Classification: **test/harness defect**. `/features/technology` returns 200 but no longer mounts
  `EntityConvergenceField`; commit `720a0650` intentionally replaced it with `EntityConvergenceWorkbenchField`
  and `__tests__/marketing/creative-experience-system.test.ts` asserts the old field is absent. Page and spec are
  identical on `main` (pre-existing). Public marketing page, not a signed-in product surface. Each failing width
  burned ~65 s of the job budget.
  Fix: spec retargeted to the shipped workbench (`entity-convergence-workbench`, `kf-a-field`, honesty copy);
  the two `kfState` freeze tests were removed because that freeze exists only on the unmounted field.
  Local run: 7/7 passed.

Tests 78–220 were not reached, so no statement is made about them. Re-classify on the next exact-SHA run.

## Billing E2E classification (CI run 36510672358, SHA `445fe3f1`)

INCONCLUSIVE_TIMEOUT. Cancelled at the 20-minute cap (02:10:18Z → 02:30:34Z) after 84 of 218 tests (78 passed).
The technology spec above passed. Failures before the cutoff:

- `e2e/canonical-ai-workspace.spec.ts` — stale selection is not sent after navigating away.
  Classification: **test/harness defect**. The Playwright webServer runs `pnpm dev`; React Strict Mode
  double-invokes the composer-intent effect in `ai-workspace.tsx` (protected seam), so the first prompt is posted
  twice and the spec read the wrong POST. The POST made from `/e2e/shots/workflows` carries `selection: null`,
  which is the product contract. Spec now asserts on the POST from the workflows route. Local: 4/4 (repeat-each 2).
  The dev-only non-idempotent effect is a core/protected-seam handoff item; production builds do not double-invoke.
- `e2e/execution-result-navigation.spec.ts` — hosted_files file chip.
  Classification: **test/harness defect**. Commit `62760765` (UX Reset Phase 7) deliberately moved artifacts
  behind an "Artifacts (N)" disclosure; the spec predates it and fails identically on `main`. Spec now opens the
  disclosure first. Local: 4/4 (repeat-each 2).
- `e2e/app-navigation-crawler.spec.ts` — `/home → Agents` console error: 403 on `/api/meson/insights`.
  Classification: **real product defect, FRONTEND WIRING DEFECT** (signed-in, pre-existing; also failed on
  `efc0c988`). `/api/meson/insights` is `require_tier("control")` + full seat (`backend/app/routers/meson.py:34`).
  The global Meson toolbar (`components/gravitre/meson-toolbar-popup.tsx`) called it as a fallback for every
  signed-in user, so free/node/trial orgs got a 403 on every app page. Fix: the fallback only fires once
  `/api/entitlements` has loaded and reports tier `control` or `command` (same rule as the server gate). Remaining
  gap, not fixed: a Lite seat on a Control+ org would still get 403 because the frontend has no seat-type signal;
  that needs core to expose seat type in `/api/entitlements` or return an empty payload instead of 403.
- `e2e/app-navigation-crawler.spec.ts` — Marketplace → Workflows sidebar navigation did not reach `/workflows`
  within 20 s. Classification: **INCONCLUSIVE**. Passed on `efc0c988`; no relevant code changed between the two
  SHAs; consistent with first-hit dev compilation of `/workflows`. Added to the owner-live walk.
- `e2e/intelligence-hub-ui.spec.ts` G5 was the test in flight when the job was cancelled — not a failure.

## Billing E2E classification (CI run 36516204107, SHA `a4d4ca25`)

INCONCLUSIVE_TIMEOUT. Required jobs (web, backend pytest, voice gate, dependency audit, Integration Smoke) passed;
Billing E2E was cancelled at the 20-minute cap (03:22:03Z → 03:42:18Z) with 81 distinct tests passed. The two
spec fixes above and the Meson fix held: no `/api/meson/insights` 403 appeared in the crawler. Failures:

- `e2e/intelligence-hub-ui.spec.ts` — G5 (both tests): `intelligence-map-canvas` not found in 60 s.
  Classification: **test/harness defect**. The fixture org is a fresh signup with no knowledge graph, so
  `resolveOverviewFieldState` reports `isEmpty` and the Overview renders its canonical empty state
  ("No knowledge graph yet", `intel-empty-sparse`) instead of the map — same on `main`. The spec asserted a map
  the fixture can never have. Fix: map-dependent tests (G5 ×2, G4, List alternative) wait for map *or* empty
  state and skip as NOT RUN when empty, matching the spec's existing "no prediction nodes" skip. Map UI remains
  unproven in CI and stays on the owner-live walk (Intelligence row).
- `e2e/app-navigation-crawler.spec.ts` — `/agents → Assignments` stayed on `/agents` past the crawler's 20 s wait.
  Classification: **INCONCLUSIVE** (same class as Marketplace → Workflows last run: a different link fails each
  run with no related code change, consistent with first-hit dev compilation). Added to the owner-live walk.

## Billing E2E classification (CI run 36531783430, SHA `af557598`)

INCONCLUSIVE_TIMEOUT. Required jobs passed; Billing E2E cancelled at the 20-minute cap (06:43:17Z → 07:03:32Z)
after reaching test 114 (88 distinct passed, 23 skipped — the Intelligence map tests now skip as NOT RUN on the
empty fixture org, as intended). Failures:

- `e2e/app-navigation-crawler.spec.ts` — `/approvals → Intelligence`: "Main content too short (20 chars)", attempt
  and retry. 20 chars is exactly the `/intelligence` Suspense fallback "Loading intelligence"; the crawler samples
  600 ms after `<main>` attaches. Classification: **INCONCLUSIVE** (dev-compile timing). The same crawler step
  passed on `efc0c988`, `445fe3f1` and `a4d4ca25`, and no app code changed between `a4d4ca25` and `af557598`
  (spec + docs only). Owner-live walk checks that Intelligence leaves its loader promptly.
- `e2e/marketing-navigation-crawler.spec.ts` — `guides-first-agent`: console error "Encountered a script tag while
  rendering React component" on `/guides → /docs/guides/how-to/agents`. Reproduced locally 1 of 4 runs.
  Classification: **real product defect, pre-existing, public marketing (not signed-in)**. Source:
  `app/(marketing)/layout.tsx` renders `components/marketing/google-tag-manager.tsx`, which emits raw inline
  `<script>` tags; when that layout mounts on a client-side navigation React 19 warns and the inline GTM/consent
  bootstrap does not execute. Both files are identical to `main`. Not fixed on this branch (GTM/consent
  behaviour is outside the 3.0 Plus frontend scope and needs an owner decision, e.g. `next/script` with
  `beforeInteractive`); tracked as a separate item.

Harness note (not changed unilaterally): 218 tests on one worker do not fit the 20-minute `timeout-minutes`, so
this job cannot produce PASS as configured. Raising the cap or sharding the suite is Cesar's call.

## Core handoff (core agent owns)

- **Capability API seam.** Build the authenticated, org-scoped, read-only capability route over the registry in local commit `573c249a` (`backend/app/capabilities/registry.py`, 12 tests). Do not duplicate it; the frontend will consume the route once it exists.
- **Autonomy rule.** Prove the canonical rule for writes when an org has no `hitl_policies`, and where `trust_level` is enforced (today: ReAct write gate and voice PSTN, not `invoke_tool`).
- **Chat panel copy (protected seam).** `components/gravitre/assistant/chat-execution-panel.tsx` states "write steps run automatically unless your approval settings require confirmation." It predates this branch and asserts the unreconciled rule; core should correct it when the rule is proven.
