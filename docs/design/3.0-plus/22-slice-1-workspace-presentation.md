# 22 — Slice 1: AI workspace presentation + Window Manager integration (Phase 8)

**Date:** 2026-09-24  
**Authority:** Cesar — "Authorize Slice 1 — AI workspace presentation + Window Manager integration"  
**Base:** Slice 0 `f4a79030` on `feat/gravitre-3.0-plus-frontend`  
**Preview:** `/dev/slice-1-workspace` (internal, fixture props, sending disabled)

## Status by layer

| Layer | Status | Evidence |
|-------|--------|----------|
| Unit / integration (vitest) | PASS (local) | `pnpm exec vitest run __tests__/gravitre __tests__/lib` — 98 files, 710 tests |
| Typecheck | PASS (local) | `pnpm exec tsc --noEmit -p .` exit 0 |
| Browser, fixture preview | PASS (local) | `slice-1-shots/slice-1-validation.json` — 39/39, Edge headless via `validate-slice1.mjs` |
| Live authenticated `/ai` | **NOT RUN** | Needs a signed-in session against a deployed build |
| Production | **NOT RUN** | Not merged, not deployed (per authorization) |

## 1. Hydration fix

**Root cause (two parts).**

1. `GravitreWindowManagerShell` read `localStorage` during render, so the server (no storage) and the hydrating client (stored preference) could render different modes.
2. The residual Slice 0 warning at the `PageIntro` eyebrow was a tooling artifact: the Cursor browser snapshot injects `data-cursor-ref` attributes before hydration. Headless Edge (no injection) shows 0 hydration errors.

**Fix.** `hooks/use-window-manager-preference.ts` — `useSyncExternalStore` with a `null` server snapshot. SSR and the hydrating render agree (contextual default), then the remembered preference applies post-hydration. Same-tab updates via the `gravitre:wm-preference` event; cross-tab via `storage`. No `suppressHydrationWarning`. The shell root exposes `data-wm-mode-source="explicit|preference|contextual"`.

**Regression coverage.** `__tests__/gravitre/window-manager-hydration.test.ts` — `renderToString` with empty storage → seed preference → `hydrateRoot`; asserts no recoverable/hydration errors, the preference is applied, cross-tab propagation works, and a control case proves a naive render-time read *is* reported.

## 2. Composition (Conversation / Work / Split)

Presentation only; one runtime. `lib/gravitre-ai-composition.ts` → `resolveWorkspaceComposition`:

- No work artifact → Conversation only (Work/Split disabled with a reason).
- Work exists → remembered preference, default Split.
- **Approval visible → Work is unavailable** (falls back to Split) so Approve/Reject is never hidden.
- In Work, the transcript is `hidden` (not unmounted) — no remount, no identity reset.

UI: `components/gravitre/ai-composition-switch.tsx` (Radix ToggleGroup, "Workspace layout", disabled reason via `aria-describedby`).

## 3. Runtime state fidelity

`lib/gravitre-ai-runtime-state.ts` derives state only from props the runtime already produces. `GravitreAIRuntimeStatus` renders it (`role="status"`, `aria-live="polite"`, nothing when idle).

| State | Production signal | Source |
|-------|-------------------|--------|
| Idle | yes | none of the below |
| Streaming | yes | `status==="streaming"` / `isStreaming` |
| Generating | yes | `status==="submitted"` / `isBusy` / `confirmExecuting` |
| Completed | yes | `executionResult.success===true`, no failed step |
| Needs approval | yes | same predicate as `ChatExecutionPanel`: `dialogueMode ∈ {confirm, awaiting_approval}` && `pendingTask.type` |
| Blocked | yes | approval visible but queued for another approver |
| Failed | yes | `status==="error"` / `executionResult.success===false` |
| Partial | yes | `canContinueAfterStop` / a failed `stepBreakdown` item |
| Resumed | **no** | No runtime signal exists. Fixture-only, labeled FIXTURE. Needs a core-agent signal before production use. |

Header presence in the preview uses the same `deriveGravitreHelperPresence` as `AiWorkspace`.

## 4. Window Manager in the real host

Seam: **no protected file edited.** `AiWorkspace` already routes non-expanded modes to `GravitreAIFloatBridge`; the bridge reads the mode via the new non-throwing `useOptionalGravitreAIWorkspace()`.

- **Docked** is the same `motion.div` as floating (`placement="docked"`), so the conversation subtree does not remount. Body gets `data-gravitre-wm-docked`; `globals.css` reserves `--g-wm-dock-width` (≥768px) so page content stays usable.
- **Floating vs compact** variants; floating defaults to 640×640 when no stored geometry.
- **Provider**: `choosePresentationMode` persists; `restoreFromHelper` returns to the mode the user minimized from, else contextual default + remembered preference (`resolvePreferredWindowMode`).
- **Behavior change (A3):** the first launcher open with no preference now resolves to `floating` (was `float`). `ai-helper.test.ts` updated.
- Mode switching never touches execution: no mode handler calls submit/approve/stop.

## 5. Shared drawers and inspectors

`components/gravitre/inspector/` — `GravitreInspector` on the shared `Sheet` for entity, evidence, artifact, approval, task, error and advanced configuration. Captures the opener and returns focus on close (Radix only restores to a `Trigger`; controlled use has none). Escape closes. Content-only — no business-state store.

## 6. Pre-existing bugs fixed along the way

| Bug | Origin | Fix |
|-----|--------|-----|
| Mobile sheet content rendered off-screen at the float snap (content 174px tall, translated 380px) | `a207cb53` (2026-09-10) | `ai-mobile-sheet.tsx`: viewport-tall content + `pb-[var(--snap-point-height)]`; composer now 791–827 of 844 |
| Mobile: pending approval covered by the auto-opened Work/Inspect overlay (Approve only reachable via "Back to conversation") | `40493b36` (Command OS) | `ai-mobile-sheet-bridge.tsx`: stay on conversation while an approval is visible and scroll the transcript to it; overlay moved below the status line. `gravitre-command-os.ts` unchanged. Approve now 681–713 of 844 |

## 7. Validation (fixture preview, headless Edge)

`slice-1-shots/slice-1-validation.json` — 39/39 PASS. Covers: hydration (slice-0 and slice-1, with and without stored preference); open at remembered preference; dock keeps page usable (420px reservation, typing beside dock); undock; expand; composition default and memory; approval never hidden (desktop and mobile); fullscreen `aria-modal` with exit + reduce, focus trap over 25 Tabs, Escape back to expanded; minimize → launcher → restore; provider instance + messages array stable across 11 transitions with exactly one surface; narrow desktop 1024 and tablet 834 dock; mobile sheet on-screen with reachable composer; desktop → mobile → desktop resize keeps identity; control names; visible focus ring; inspector Escape + focus return; reduced motion.

Screenshots: `01`–`13` in `slice-1-shots/` (light and dark; desktop, narrow, tablet, mobile; keyboard focus).

## 8. Out of scope / not done

- Slice 2 (not started).
- Live authenticated `/ai` validation and production — **NOT RUN**.
- Show-the-work (placement only), RF Option B (direction only).
- Auth gating unchanged: the helper still requires a session (`mayShowGravitreAIHelper`); the preview has no chat runtime.

## 9. Core-agent coordination

1. **Resumed** needs a runtime signal (e.g. a resumed-run flag on the turn) before it can show outside fixtures.
2. Mobile sheet and mobile bridge fixes (section 6) touch the surfaces core renders on mobile — no protected file changed, but core should know.
3. In `ai-workspace.tsx`, expand/fullscreen transitions call `setPresentationMode` (not persisted) — the preference only records them on minimize. Persisting on every transition would need a one-line coordinated change there.
