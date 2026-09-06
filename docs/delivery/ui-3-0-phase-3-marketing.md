# GRAVITRE UI 3.0 — PHASE 3 MARKETING (HYBRID A+B)

**Date:** 2026-09-06  
**Status:** **ACCEPTED 2026-09-06** — Hybrid A+B light marketing accepted locally; awaiting commit/push/deploy for `gravitre.app` evidence  
**Prior:** Phase 2 ACCEPTED · Hybrid A+B · light-first tokens  

---

## What landed

| Area | Change |
|------|--------|
| Marketing chrome | `void` → **`daylight`**; force `light` theme; black logos |
| Hero | Hybrid A+B split: copy left + `HybridHeroStage` / `ProductStage` living beats |
| Atmosphere | Soft neutral spotlight — no hero IntelligenceField / grid |
| Home sections | Reduced field opacity; light IntegrationsGrid; mineral canvas tokens |
| A11y | Headline no longer concatenates `for`+`your` without space |

### Key files

- `apps/web/components/marketing/marketing-chrome.tsx`
- `apps/web/components/marketing/home/hero-parallax.tsx`
- `apps/web/components/marketing/home/hybrid-hero-stage.tsx`
- `apps/web/app/(marketing)/page.tsx`
- `apps/web/components/marketing/home/home-narrative-sections.tsx`
- `apps/web/components/marketing/home/marketing-spotlight.tsx` (`neutral` tone)

---

## Visual evidence (local)

- Local capture: `http://127.0.0.1:3010/` — light mineral hero, black wordmark, emerald CTAs, ProductStage with Trace + beat chips.
- **NOT production PASS** — `gravitre.app` still Pass 3 dark until deploy + alias + live re-shot.

Honest craft notes from local hero shot (`docs/delivery/ui-3-0-phase-3/`):

- Light-first + product-stage direction reads clearly vs prior dark void.
- Stage chrome / Trace / beat chips (Tool running, Verified, etc.) visible.
- Fixture product PNGs are themselves light mineral UI — at hero scale they can read sparse; refine with denser crops / layered A panels in a follow-up if Cesar wants more visual density before deploy.
- Marketing ≥9 craft **not claimed** until Cesar visual accept + prod deploy evidence.

---

## Explicit non-goals (this phase)

- No full Nucleo migration  
- No Playwright goldens committed  
- No desktop / extension / mobile app shells  
- No invented Trusted-by / ROI  
- App ThemeProvider still restored on leave marketing  

---

## Accept → next

**ACCEPTED** by Cesar (2026-09-06).

Next (needs explicit ask): **commit → push → deploy** → live `gravitre.app` screenshot (prod evidence bar).

Then **Phase 4** web-app shell (dense calm mineral; low motion), or density refine on hero product crops if preferred first.
