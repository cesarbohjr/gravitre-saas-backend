# GRAVITRE_WINDOW_STATES.md

**Authority:** Subordinate to `GRAVITRE_3_0_PLUS_MASTER_SPEC.md` (§15). Detail + repo mapping: `docs/design/3.0-plus/06-window-architecture.md`.  
**Phase:** 5 consolidation + Phase 6 harness (`?s=window-manager`).

## Required modes

Compact · Floating · Docked · Expanded · Fullscreen · Minimized · Restored

## State that must survive transitions

Conversation · Artifacts · Current agent task · Workflow context · Voice · Approval · Execution status · Inspector selection

## Composition (not scale)

| Mode | Prioritize |
|------|------------|
| Compact | Conversation, task, essential progress, one primary action, voice if active |
| Floating | Conversation, artifact preview, execution, approval, progress, resize/reposition |
| Docked | Side persistence with page context still visible (harness prototype) |
| Expanded | Conversation, artifact, task, approval, progress, supporting context |
| Fullscreen | Conversation, artifact workspace, inspector, execution, sources/evidence, advanced controls |
| Minimized | Task chip + progress + restore |
| Restored | Explicit return to last meaningful composition |

## Floating UI (§14)

Anchored menus/popovers/tooltips/command/inspectors only — **not** the Window Manager.

## Production gate

**G-STRUCT PASSED 2026-09-24** — Option A: contextual default + remembered preference; docked is **not** the universal default. Slice 0 may ship the presentation shell. Full provider→runtime docked cutover still requires identity-preservation evidence and coordinated soft-conflict review.
