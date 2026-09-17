# GRAVITRE UX RESET 1.0 — Phase 4 report

**Slice:** Motion between compact / expanded / fullscreen of the **same** physical workspace. Minimized stays the helper launcher (no window morph). Mobile sheet unchanged (vaul).

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Shared Framer `layoutId` `gravitre-ai-workspace-frame` on compact (float) and expanded/fullscreen shells.
- `GRAVITRE_AI_WORKSPACE_LAYOUT_ID` in `gravitre-ai-presentation.ts`.
- `LayoutGroup id="gravitre-ai-workspace"` on `GravitreAIWorkspaceHost` so portaled compact/expanded frames share layout identity.
- Stable React keys `gravitre-ai-float` / `gravitre-ai-shell` on the exclusive desktop shells.

AnimatePresence was **not** wrapped around the bridges: those are not motion nodes (the `motion.div` lives inside a portal). Wrapping them delayed first mount in Playwright.

## Changed

- Frame enter/exit duration uses `MOTION.major` (400ms). `prefers-reduced-motion` drops `layoutId` and uses duration 0.

## Removed

- Instant chrome swap without a shared layout identity (shells still exclusive; morph is layout, not two runtimes).

**Not changed:** runtime owner (`useChat` in `AiWorkspace`), drag geometry, kill-switch XOR, marketing isolation, mobile vaul sheet.

---

## A. Result

Phase 4 is **source PASS** (Vitest `phase-4-workspace-motion.test.ts`, 2 tests). Live morph in production: **NOT PROVEN** until this commit is on the production alias.

Also: chat-surface-drift treats `/agents/[id]/chat` as a canonical summon (no second composer).
