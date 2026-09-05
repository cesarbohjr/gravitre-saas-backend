# Advanced Design — tranche 2 (2026-09-04)

**Program:** Canvas plan continuation after approved research board + pilot `0ffc63d6` (already on `origin/main`).

## This tranche

| Item | Change |
|------|--------|
| QuestionTool ADAPT | Retokened `clarification-message.tsx`; wired in `chat-transcript` when `dialogueMode === "clarify"` (last assistant). No invented suggestion chips. |
| EditTool ADAPT | `pre-action-card.tsx` STATUS/Nucleo header chrome; risk chips → `STATUS.*`. Same Approve/Reject/Modify handlers. |
| Marketing TRACE | `MarketingTracingBeam` in HowItWorks; lines on How-it-works section. |
| Composer | Stop button uses `--status-pending` (was hard amber). |
| Empty states | Icon tile uses `RADIUS.tile`. |

## Non-claims

- No layout/IA change intended (pl-8 on HowItWorks steps is padding for TRACE rail only — same two-column grid).
- No AgentChat shell; no Aceternity on ops screens.
- Voice human verify still separate.

## Verification

- `npx tsc --noEmit` (apps/web) — **PASS**
- `node scripts/check-chat-surface-drift.mjs` — **PASS**

## Next (canvas §J remaining)

Dashboard / Agents / Workflows / Runs / Connectors / GIBE / Marketplace / Settings STATUS+Nucleo polish; Design Mode review; §64 acceptance pack.

## Customer surfaces

No new prices/claims/badges/Enable toggles. **(a)** Approved visual augmentation.
