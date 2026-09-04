# GRAVITRE UI 2.0 — Pilot E (Voice) delivery

**Date:** 2026-09-04  
**Scope:** Canonical Wave / Orb / Visualizer aliases + CSS vars + drift CI mutation — no new visual language

---

## Aceternity pre-check

| Path | Result |
|------|--------|
| CLI `npx shadcn@latest view @aceternity/background-beams --cwd apps/web` | **PASS** — registry returns Background Beams item |
| shadcn MCP `@aceternity` | Requires MCP reload with `--cwd apps/web` (monorepo). CLI is the evidence bar for this pilot. |

---

## What shipped

| Item | Change |
|------|--------|
| `GravitreWave` | Alias of `GravitreVoiceWaveform` |
| `GravitreOrb` | Extracted orb circle; `VoiceOrbTakeover` composes it |
| `VoiceStateVisualizer` + `resolveVoiceVisualizer` | Maps client `VoicePresenceState` → shared Wave (no second bar DOM) |
| CSS vars | `--gv-voice-*` in `app/globals.css`; Wave/Orb use vars (no hard-coded hex in presentation) |
| Consumers | Shared composer, presence strip, e2e shots, agent voice assignment → `GravitreWave` |
| Drift CI | Owns Orb/Wave/Visualizer exports; bans MarketingGravitreOrb forks; orb circle hand-rolls |

**Honesty:** Duplex presence remains **client UX** — not PSTN `VoiceSessionStatus` parity.

---

## Verification evidence

| Check | Result |
|-------|--------|
| `node scripts/check-chat-surface-drift.mjs` | **PASS** — `chat-surface-drift PASS` |
| Class B mutation (temp file with `gv-wave-bar`) | **PASS** — exit 1 with hand-roll message; restore → PASS |
| Lints on voice presentation / presence / composer | Clean |

**NOT RUN (this pass):** Live `/ai` mic audio; Railway deploy. Visual complete ≠ voice FINAL audio gate.

---

## Files touched

- `apps/web/components/gravitre/assistant/voice-presentation.tsx`
- `apps/web/components/gravitre/assistant/voice-session-presence.tsx`
- `apps/web/components/gravitre/assistant/shared-chat-composer-controls.tsx`
- `apps/web/components/gravitre/agent-voice-assignment.tsx`
- `apps/web/app/e2e/shots/voice-states/page.tsx`
- `apps/web/app/globals.css`
- `scripts/check-chat-surface-drift.mjs`
- `.cursor/mcp.json` (shadcn `--cwd` for monorepo)
