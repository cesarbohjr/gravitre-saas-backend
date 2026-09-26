# 25 — Phase 8 Area 15 acceptance record

**Branch:** `feat/gravitre-3.0-plus-frontend` (not merged, not deployed).
**Status:** BLOCKED on owner-authenticated visual capture. See "Visual acceptance".

## Visual acceptance

NOT RUN. The capture harness (`visual-capture-all.mjs`, persistent Edge profile) requires a
session whose account or linked identity is `cesar.bohorquez.jr@gmail.com`. Every session
observed in the capture window was `cesar@gravitre.app` with a single linked identity
`google:cesar@gravitre.app` (harness log, 2026-09-25). No screenshots were taken, so no
before/after, breakpoint, theme, or cross-route visual claim is made here.

Code-level convergence landed without screenshots (each commit on the branch):

| Commit | Scope |
|--------|-------|
| `6b76c40d` | Marketplace / Goals / Assignments / Admin labels, dark `bg-white` surfaces, Goals row list, dead Assignments Filter removed, Admin Intelligence back on shared tabs, sentence-case labels |
| `ae8af8e3` | Link-wrapped buttons replaced with `Button asChild` (invalid nested interactive elements) |
| `6073e810` | Light-theme contrast pairing for `text-*-300/400` accents; chart colors on theme tokens |
| `643e6454` | Workflow Builder inner panels (visual only): labels, progress token, hover, floating toolbar, shadows |

## E2E / CI classification

Evidence: CI run 36202998402 on `7ecc7336`; local Playwright runs against `pnpm dev` with Edge.

| Test | Class | Evidence and disposition |
|------|-------|--------------------------|
| `canonical-ai-workspace.spec.ts:11` | A (test not updated for approved A3) | First open resolves to `floating` per `22-slice-1-workspace-presentation.md`. Spec updated in `7ecc7336`; passes locally and in run 36202998402. |
| `canonical-ai-workspace.spec.ts:247` | B (protected runtime) | Dev-only duplicate submit. With React Strict Mode, `AiWorkspace`'s composer-intent effect runs twice on mount and calls `submitPrompt` twice (local `chatSubmitCount: 2`). With `reactStrictMode: false`: one POST, `mountCount: 1`. Production does not double-invoke effects. Dependency: guard the effect in `app/ai/_components/ai-workspace.tsx` by `composerIntent.nonce` (same pattern as `initialPromptSentRef`). Not edited here. |
| `execution-result-navigation.spec.ts:4` | C (stale test) | `main` changed the label to `Open in Apollo` on 2026-09-17 (`62760765`); spec last touched 2026-09-10. Spec aligned in `7ecc7336`. |
| `execution-result-navigation.spec.ts:40` | B / C (protected surface) | `ChatExecutionPanel` no longer renders `file-reference-chip` in the harness. No branch diff to the panel, harness or spec. Needs the core agent to say whether the chips moved intentionally. |
| `billing-overview-failure-no-node-default.spec.ts:17` | C (harness) | Post-login redirect destroyed the context in `setSelectedOrg`. Fixed in `1e0a4496`; passes in run 36193867023. |
| `app-navigation-crawler.spec.ts:30` | C (stale test) | Item list predated the IA consolidation (fixed in `7ecc7336`, unit sync test added). `/ai` opens a fullscreen `aria-modal` dialog (existing on `main`) that covers the sidebar; crawler now returns to the seed page when that dialog is up and reads its text for the content check. |
| `creative-pilot3-knowledge-fabric-widths.spec.ts` (9) | C (existing repo failure) | `EntityConvergenceField` is only mounted in a dev prototype, never on `/features/technology`. No branch diff to marketing. Mounting it would add marketing claims, so it is left for an authorized owner. |
| Billing E2E job timeout | C (CI infrastructure) | Job runs the full suite (`npm run test:e2e`, 218 tests, 1 worker) under `timeout-minutes: 20`; run 36202998402 reached test 70. No completed run in the last 200 CI runs. `ci.yml` marks the job "Manual/signal only — do not run on main push". Timeout / sharding is shared CI config and is not changed here. |

Push-gated jobs on `7ecc7336` (run 36202998402): Backend (pytest), Web (lint + typecheck + build),
Integration Smoke Test, Dependency audit, Shared runtime text/voice gate — all success.

## Protected core dependencies

1. `app/ai/_components/ai-workspace.tsx` — make the composer-intent effect idempotent per nonce.
2. `components/gravitre/assistant/chat-execution-panel.tsx` — confirm or restore hosted-file chips for `hosted_files` results.

## Remaining to accept Phase 8

1. Owner-authenticated capture (all sets), review, fixes, baseline commit.
2. Exact-SHA CI on the final release candidate after the capture fixes.
3. Cesar's merge and deploy approval.
