# GRAVITRE UI 2.0 — Pilot C (Agents) delivery

**Date:** 2026-09-04  
**SOT:** `AgentStatus` = `active | idle | processing | error` (`apps/web/types/api.ts`)  
**Shared presenter:** `apps/web/lib/agent-runtime-status.ts`

---

## Where to see UI 2.0 pilot changes

Run the web app (`pnpm dev` / `pnpm --filter web dev` as you usually do), then open:

| Pilot | Route | What to look for |
|-------|-------|------------------|
| **E Voice** | `/ai` (composer mic / orb) · `/e2e/shots/voice-states` (design harness; not prod) | `GravitreWave` / orb; CSS voice tokens |
| **A Marketing** | `/` (marketing home) | First viewport: brand · headline · CTAs · beams; no pill cluster |
| **B Dashboard** | `/home` (signed in) | `PageHeader`, approval/confidence chips, no fake confidence chart |
| **C Agents** | `/agents` roster · `/agents/[id]` profile | Chips: **Active / Idle / Running / Failed**; pulse only on Running |

---

## What shipped (C)

| Item | Change |
|------|--------|
| Labels | `processing` → **Running**, `error` → **Failed** (not Training/Limited) |
| PULSE | Orb rings / beacon pulse **only** when `status === "processing"` |
| Stats | Total · Active · Running · Failed (API counts) |
| Ambient | Removed MorphingBackground / NeuralNetwork / GlowOrbs / ParticleField on roster |
| Profile | Removed invented “Training Progress” bar (was successRate); honesty success-rate card |
| Tasks | `taskRuntimeLabel` includes **Needs input** for paused / needs_human_input / awaiting_approval |

**OUT:** TRAINED / healthy / Limited / Training remaps.

---

## Customer-surface declaration

**(a)** No new prices, TRAINED badges, or Enable toggles. Status copy maps existing API enum only.

---

## Verification

| Check | Result |
|-------|--------|
| Lints agents pages + runtime status lib | Clean |
| Live Class A: one running + one failed chip in prod | **NOT RUN** |

---

## Files

- `apps/web/lib/agent-runtime-status.ts` (new)
- `apps/web/app/agents/page.tsx`
- `apps/web/app/agents/[id]/page.tsx`
