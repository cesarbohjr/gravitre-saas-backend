# GRAVITRE UX RESET 1.0 — Phase 4 report

**Slice:** Motion between compact / expanded / fullscreen of the **same** physical workspace. Minimized stays the helper launcher (no window morph). Mobile sheet unchanged (vaul).

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Shared Framer `layoutId` `gravitre-ai-workspace-frame` on compact (float) and expanded/fullscreen shells.
- `GRAVITRE_AI_WORKSPACE_LAYOUT_ID` in `gravitre-ai-presentation.ts`.

## Changed

- Frame enter/exit duration uses `MOTION.major` (400ms). `prefers-reduced-motion` drops `layoutId` and uses duration 0.

## Removed

- Instant chrome swap without a shared layout identity.

**Not changed:** runtime owner (`useChat` in `AiWorkspace`), drag geometry, kill-switch XOR, marketing isolation.

---

## A. Result

Phase 4 is **source PASS**. Live morph in production: **NOT PROVEN** until the deploy that includes this commit.

Also: chat-surface-drift now treats `/agents/[id]/chat` as a canonical summon (no second composer).
