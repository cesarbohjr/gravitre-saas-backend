# GRAVITRE × NODUS — VISUAL PARITY PLAN (vs Aceternity preview)

**Date:** 2026-09-06  
**Status:** **ACTIVE — Phases 5–8 on main** (marketing + auth + app shell PLATFORM-ADAPT); await deploy for product chrome  
**Preview SOT:** https://ui.aceternity.com/template-preview/nodus-agent-template  
**Live today:** https://gravitre.app/ updates after Vercel redeploy of `main`


---

## Why gravitre.app looks unchanged

Phase 3–4 only shipped **tokens, fonts, light-first theme, and cross-platform color bridges**.  
It did **not** replace homepage sections, navbar, or marketing chrome with the licensed Nodus template layout. Production therefore still renders the old “one AI brain” marketing composition.

---

## Target = Nodus template, Gravitre identity

| Dimension | Match preview | Gravitre delta |
|-----------|---------------|----------------|
| Section order (home) | Hero → HeroImage → LogoCloud → HowItWorks → AgenticIntelligence → UseCases → Benefits → Testimonials → Pricing → Security → FAQs → CTA | Keep order; **real Gravitre logo**; strip unverified Gartner / fake prices / fake logos |
| Accent | Coral/orange `#f17463` | **Green `#16a374`** (`--brand` / `text-brand`) |
| Type | Inter Display + DM Mono | Already wired in web root |
| Theme | Preview often defaults dark | **Light-first only** (Nodus *light* composition: white canvas, charcoal type, green accent) |
| Nav | Pricing / About / Careers / Blog + Start building | Same Nodus chrome pattern; logo = Gravitre; CTA → `/get-started`; keep essential Gravitre routes reachable (Features/Docs via footer or secondary) |
| Product shot | Template dashboard PNG | Real Gravitre `/ai` (or product) capture in same parallax frame |
| Auth | Template sign-in/up pages | Adapt visuals; **keep Gravitre auth wiring** |
| App / desktop / extension | Not in zip | **PLATFORM-ADAPT** same tokens after marketing lands |

---

## Implementation phases (remaining)

| Phase | Deliverable | Changes live site? |
|-------|-------------|-------------------|
| ✅ 0 | Inventory + Cesar decisions | No |
| ✅ 3–4 | Tokens, fonts, green, light-first bridges | Subtle (fonts/primary) if redeployed; layout still old |
| ✅ 5–7 | Marketing homepage + routes + auth chrome | Yes |
| ✅ 8 | App shell PLATFORM-ADAPT | Product UI |
| 9 | Desktop + extension denser adapt | Non-web |
| 10 | Residue audit (Notus/orange/fake claims) | Hardening |

---

## Phase 5 acceptance (homepage)

Must look like the Aceternity Nodus preview **structure** on light canvas with green accent:

1. Border-divided centered hero (badge shimmer, H1 with green keyword, dual CTAs)
2. Parallax product stage in gray dotted frame (corner dots)
3. Subsequent sections in Nodus order (placeholders OK only if labeled or removed when claims are fake)
4. Nodus-style navbar/footer with **Gravitre** mark
5. No orange. No Gartner claim. No invented prices on home pricing block until authorized plans wired

---

## Scaffold honesty

**(a)** Full visual match to licensed template + green brand explicitly requested.  
Demo economics / compliance badges from the zip must **not** ship as Gravitre product truth.

---

## Cleanup note (2026-09-06)

Abandoned Phase-8 chat/Nucleo WIP, probe JSON, and `.tmp_*` artifacts discarded. Working tree clean on `main` after `ea3c79b5`.
