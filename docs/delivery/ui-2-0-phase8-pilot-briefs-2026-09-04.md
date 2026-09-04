# GRAVITRE UI 2.0 — Phase 8 pilot briefs

**Date:** 2026-09-04  
**Mode:** Pilots E–D complete 2026-09-04. Phase 9 tokens/reskin tranche 1: `ui-2-0-phase9-tokens-reskin-2026-09-04.md`.  
**Depends on:** Phases 2–6 proposals + Phase 7 tools

---

## How to choose

| Pilot | Risk | Impact | Best if you want… |
|-------|------|--------|-------------------|
| **A — Marketing** | Medium (public) | Brand signal | First visual “wow” without touching product chrome |
| **B — Dashboard** | Medium | Daily ops | Product-feel upgrade where users live |
| **C — Agents** | Medium–High | Status honesty | AI state matrix proof |
| **D — GIBE** | Higher (complex) | Intelligence surface | Hardest visual system under DS 2.0 |
| **E — Voice** | Medium (shared path) | Continuity | Canonical Wave/Orb without surface forks |

Recommended order for least blast radius → highest learning: **E → A → B → C → D**.

---

## Pilot A — Marketing hero / landing

**Scope:** First viewport of primary marketing route(s) only — brand, one headline, one support line, one CTA group, one dominant visual. No new prices/claims/Enable.

**KEEP:** Route IA, copy unless you authorize rewrite, CTA destinations.  
**REFINE:** Motion density; use Motion tokens + `useMotionPrefs`.  
**RESKIN:** Zinc island → semantic brand tokens (light-first).  
**SHARE:** Logo + primary CTA styles with app.  
**EXTERNAL (optional):** One Aceternity-style background effect **or** one 21st motif — extracted and retokened.  
**OUT:** Card grids, stat strips, pill clusters in hero.

**Verify:** Desktop + mobile first viewport; reduced-motion static; no invented product claims.  
**Approval:** Safe to start after token choice for marketing light lock.

---

## Pilot B — Dashboard / home hub

**Scope:** Main authenticated home / dashboard shell: PageHeader, key status chips, primary lists/tables — not every widget rewrite.

**KEEP:** Data sources, layout regions, navigation destinations.  
**REFINE:** Adopt `PageHeader` + TYPE; status chips from Phase 4 matrix where data exists.  
**RESKIN:** Surfaces/borders onto DS 2.0 elevation.  
**SHARE:** Table/header patterns with other hubs.  
**OUT:** Fake KPIs, TRAINED badges, ROI numbers.

**Verify:** Empty/error honesty; Class A screenshot of header + one live status chip with real backend state.  
**Approval:** Safe after Phase 5 token names locked for status.

---

## Pilot C — Agents status surface

**Scope:** Agents list/detail status presentation mapped to real Session/ReAct/job states.

**KEEP:** Agent APIs, actions, filters.  
**REFINE:** Labels + visual states from Phase 4 matrix (Running / Needs input / Failed).  
**PULSE/TRACE:** Motion only when backend says active.  
**OUT:** Invented “healthy/TRAINED” without runtime evidence.

**Verify:** At least one live agent job/session state → correct chip; failed path visible.  
**Approval:** Confirm which agent status enum is SOT for the chosen UI surface before coding.

---

## Pilot D — GIBE / intelligence

**Scope:** One intelligence landing or model-status strip — Module C honesty labels only.

**KEEP:** Confidence honesty / runtime_status path; no catalog TRAINED as live.  
**REFINE:** Typography + empty/estimate/data_gate presentation.  
**EXTERNAL:** Optional Three/network only with **explicit approval** + reduced-motion fallback.  
**OUT:** Fake TRAINED, SOC claims, Enable toggles.

**Verify:** STA-331-aligned labels against a known honesty fixture; no overclaim.  
**Approval:** Required before any WebGL.

---

## Pilot E — Voice (recommended first technical pilot)

**Scope:** Canonical aliases only — no new visual language yet unless you expand.

1. Export `GravitreWave` = `GravitreVoiceWaveform`, `GravitreOrb` from takeover internals, `VoiceStateVisualizer` mapper.  
2. Ensure SharedChatComposerControls + VoiceOrbTakeover + presence still one DOM path.  
3. Map hex literals → CSS vars (REFINE).  
4. Extend drift CI ownership for Orb/Wave/Visualizer names.  
5. **Mutation-test** the drift script (Class B) before calling voice visual complete.

**KEEP:** Backend voice gateway + client VoicePresenceState (document client-only duplex).  
**OUT:** MarketingGravitreOrb fork; claiming PSTN parity for chat duplex.

**Verify:**  
- Local: voice-states e2e / existing shots  
- Drift CI green + mutation (break import → CI fails)  
- Cross-surface: `/ai` + marketing demo import if any  

**Approval:** Safe to start immediately; visual polish can follow tokens.

---

## STOP

Do **not** implement all five. Pick one pilot (or Phase 9 token cleanup only). Broad reskin = later phases after pilot PASS with evidence.
