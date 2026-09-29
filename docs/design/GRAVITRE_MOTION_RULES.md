# GRAVITRE_MOTION_RULES.md

**Authority:** Subordinate to `GRAVITRE_3_0_PLUS_MASTER_SPEC.md` (§26) and voice (§25).  
**Phase:** 5 consolidation.

## Libraries

| Tech | Use | Do not |
|------|-----|--------|
| Motion / Framer Motion | Entry/exit, layout, window states, micro-interactions, progressive disclosure | Sprawl without MotionProvider / reduced-motion |
| GSAP | Complex sequences, scroll-linked, marketing demos | Simple product chrome interactions |
| Three.js / WebGL | High-value spatial / storytelling only | Futurism for its own sake |

## Principles

- Motion communicates **state**, not decoration.
- Respect `prefers-reduced-motion`.
- Window mode transitions must preserve conversation/task/voice/approval/artifact state.
- Live workflow overlays: only when runtime emits real state — no fake busy theater.
- Show-the-work: no simulated browser/computer activity.

## Voice visuals (§25)

GravitreOrb + GravitreWave + VoiceStateVisualizer are canonical across compact/floating/expanded/fullscreen/desktop/mobile. States: Idle, Listening, Processing, Speaking, Interrupted, Error. Orb must not dominate small windows or vanish after minimize.
