# 21 — Slice 0 foundation (Phase 8)

**Date:** 2026-09-24  
**Authority:** G-STRUCT selected · Slice 0 authorized (`20-g-struct-decision-package.md`)  
**Preview:** `/dev/slice-0-foundation`

## Scope delivered

| Step | Deliverable |
|------|-------------|
| 0.1 | `--g-wm-*` tokens (light + dark) · `PAGE_FAMILY` / `WINDOW_CHROME` in `lib/design-system.ts` |
| 0.2 | `PageIntro` production component · existing Button/Input primitives verified against RADIUS |
| 0.3 | `lib/gravitre-window-manager.ts` (Option A policy) · `components/gravitre/window-manager/*` · docked + floating + compact/expanded/fullscreen/minimized/restored · identity preservation |

## Explicitly out of scope

- React Flow cutover  
- Areas 4–15 production migration  
- Editing `ai-workspace.tsx` / chat API / execution panels  
- Second AI / task / voice runtime  
- Show-the-work event stream  

## Soft-conflict note

`gravitre-ai-presentation.ts` and `chat-window-state.ts` gained `floating` / `docked` vocabulary. Provider accepts the modes via existing `GravitrePresentationInput` alias. Full host/bridge mount of docked beside live `AiWorkspace` remains a coordinated follow-on (Slice 0 shell is presentation-ready; live remount path not forced).

## Evidence

| Artifact | Path / pointer |
|----------|----------------|
| Preview | `/dev/slice-0-foundation` HTTP 200 |
| Light tokens/primitives | `docs/design/3.0-plus/slice-0-shots/01-slice0-light-tokens-primitives.png` |
| Dark tokens | `docs/design/3.0-plus/slice-0-shots/02-slice0-dark-tokens.png` |
| Dark WM docked + identity | `docs/design/3.0-plus/slice-0-shots/03-slice0-dark-wm-docked.png` |
| Unit tests | `vitest` — presentation / WM policy / chat-window-state / controls / provider — **62 passed** |

## Phase 7 layer note (post Slice 0)

| Layer | Status |
|-------|--------|
| Structural selection | SELECTED |
| Harness validation | PARTIAL (unchanged sufficiency for Slice 0) |
| Production integration | Slice 0 foundation landed; host/bridge docked remount **pending** |
| Human acceptance of full product UX | PENDING |
