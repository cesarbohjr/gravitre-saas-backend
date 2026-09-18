# GRAVITRE UX RESET 1.0 — live proof slice

**Slice:** morph, voice/tools across resize, AuthGate logout, agent-scoped stream, Intelligence I11 hub. Same `useChat` owner. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## What this is

Playwright against `/e2e/shots/*` (fixture session + mocked `/api/chat`). Not a logged-in production session on gravitre.app. Not a real microphone / STT socket / connector READ.

---

## Added

- Shared `data-gravitre-workspace-layout-id` on compact and expanded/fullscreen frames.
- Debug `voicePresence` + test `setVoice`.
- E2E-only `__GRAVITRE_AUTH_TEST.clearSession` (gated on `NEXT_PUBLIC_PLAYWRIGHT_E2E`).
- Shots route `/e2e/shots/intelligence` for I11 hub chrome without `page-context`.
- Spec `e2e/ux-reset-live-proof.spec.ts`.

## Changed

- Live Intelligence hub e2e **skips** when `PLAYWRIGHT_SKIP_BACKEND=1` or billing fixtures are missing (avoids `setSelectedOrg` on a destroyed context).

---

## Production deploy

Frontend **READY** `dpl_9Sgmgc2W1MP7165H2VyedEM5hQj7` @ `f8960857601c8d75e666d165d0b52c4262b6cdb3`, aliased to `gravitre.app`. Railway skipped (no backend change).

Authenticated `https://gravitre.app/ai` → `/login` (Welcome back). Production click-through **NOT PROVEN**. No local `e2e/.fixtures/billing-users.json`; I11 live login tests remain skipped. Do not seed production billing users without an explicit choice.

---

## Results (harness)

| Item | Harness | Production authenticated |
| --- | --- | --- |
| Compact → expanded morph, shared layout id, larger frame, one runtime | **PASS** when the spec is run | **NOT PROVEN** |
| Voice + in-flight mocked stream across expand | **PASS** (same runtime; duplex publishes `idle` without a mic) | Hardware STT/TTS **NOT PROVEN**; live connector READ **NOT PROVEN** |
| AuthGate logout unmounts helper + runtime | **PASS** (session clear, no `/login` redirect) | Real Supabase logout **NOT PROVEN** |
| Agent-chat mocked stream completes in-scope | **PASS** | Live agent + model **NOT PROVEN** |
| I11 seven hub links, no Training | **PASS** on shots | Live `/intelligence` login **SKIPPED** without backend fixtures |

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications.
