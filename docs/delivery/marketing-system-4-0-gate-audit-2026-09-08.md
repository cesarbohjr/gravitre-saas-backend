# GRAVITRE MARKETING SYSTEM 4.0 — GATE AUDIT

**Date:** 2026-09-08  
**Status:** **APPROVED** (Cesar, 2026-09-08) — Phase 1–3 pilot in progress / shipping  
**Canvas:** `canvases/marketing-system-4-0-gate-audit.canvas.tsx`  
**Method:** Static inventory of `apps/web/app/(marketing)` + `components/marketing`. Not a live Aceternity pixel PASS.

---

## Verdict

Homepage is high-fidelity Nodus. Most inner pages share chrome (`MarketingChrome` + `MarketingPageHero` / rails) but **do not extend** homepage motion, product staging, or graphic language. Footer is **one shared component** (good consolidation) but **medium finish** — no signature closing visual. Motion is almost entirely **framer-motion** + CSS orbits; **GSAP/Lottie unused**; **WebGL** only on auth MeshGradient.

End state required: one complete Gravitre marketing template — not “Nodus homepage + generic SaaS pages.”

---

## A — Full marketing route inventory (28)

| Route | Fidelity | Motion | Graphic | Priority | Signature visual (recommended) |
|-------|----------|--------|---------|----------|--------------------------------|
| `/` | High | FM + canvas + CSS | HeroImage, PixelatedCanvas, CTAOrbit | P0 | Keep SOT; optional 1 WebGL brain later |
| `/pricing` | High→Med | FM, SlidingNumber | Scale icons | P0 | Plan→role→outcome FLOW |
| `/features` | High | Same as home | Same as home | P0 | Agents coordinate→resolve (not home clone) |
| `/features/technology` | Medium | FM orbit | Custom GIBE orbit | **P0 pilot** | Knowledge→evidence TRACE graph |
| `/features/extension` | Medium | FM fades | BrowserFrame shots | P1 | Overlay→approval→outcome |
| `/features/marketplace` | Med→Low | AnimatePresence | Icon cards | P1 | Pack readiness→gate→live |
| `/about` | Med→High | none | Panels | P1 | Departments converge |
| `/careers` | Med→High | none | Nodus icons | P2 | Ownership timeline |
| `/contact` | Med→High | none | Logo | P1 | Soft signal field |
| `/login` `/get-started` | High | FM | **WebGL MeshGradient** | P0 | Keep mesh; consider slim footer |
| `/forgot-password` | High | FM | WebGL | P2 | Resolve on success |
| `/security` | Medium | fade-up | Lucide | P1 | Governance FLOW |
| `/blog` `/blog/[slug]` | Medium | stagger / none | Post art | P2 | Featured product stage |
| `/docs` | Medium | none | Lucide | P1 | System map nodes |
| `/docs/[...slug]` | Low–Med | DocPageMotion | — | P2 | Token align only |
| `/docs/faq` | **Low** | accordion | — | P1 | Align to MarketingRails |
| `/docs/integrations` | **Low** | none | Brand SVGs | P1 | Connector hub |
| `/docs/api/swagger` | Low | none | Swagger | P2 | Utilitarian header |
| `/api` | Medium | fade-up | Code | P1 | Request→audit TRACE |
| `/changelog` | Medium | stagger | Spine | P2 | Resolve markers |
| `/roadmap` | Med→Low | fades | Vote cards | P2 | Sticky CONNECT→LEARN |
| `/guides` | Med→Low | FM | Images | P2 | Learning path FLOW |
| `/support` | Medium | FM | Lucide | P2 | Calm escalation |
| `/download` | Medium | FM + parallax | **Grid + IntelligenceField** | P1 | Nodus product stage (retire parallel FX) |
| `/privacy` `/terms` | Medium | fade-up | — | P2 | Rails/type only |

**Homepage special-case:** Yes — full Nodus section stack without `MarketingPageHero`. `/features` is the only inner page that reuses most home motion sections.

---

## B — Footer audit

| Item | Finding |
|------|---------|
| SOT | `components/marketing/nodus/footer.tsx` via `MarketingChrome` |
| All marketing pages same footer? | **Yes** — consolidated |
| Alternate marketing footers? | **No** |
| Tokens | `--footer-link`, charcoal CTA, gray labels — Nodus-aligned |
| Motion | None |
| Closing visual | **Missing** (Part 16 gap) |
| vs vendor | Slimmer grid (6 vs 8); no newsletter/social (intentional product fork) |
| Auth caveat | Full site footer still under login/signup |

**Prototype (P):** denser columns + Resources/Enterprise + calm TRACE/mineral closing motif + restrained CTA motion. Not a second hero.

---

## C — Motion inventory

- **Primary:** `framer-motion` across ~50 marketing files  
- **Ambient CSS:** CTAOrbit / conic spins  
- **Canvas 2D:** PixelatedCanvas  
- **WebGL:** MeshGradient (auth only)  
- **Absent:** GSAP, ScrollTrigger, three.js, live Lottie usage  
- **Anti-pattern:** default `whileInView` fade-up on many inner pages (security, legal, api)

---

## D — Graphic inventory

| Live | Orphan / debt |
|------|----------------|
| HeroImage, CTAOrbit, Nodus skeletons | LivingMineralField (app intelligence) |
| Auth MeshGradient | pre-Nodus particle/hero-parallax/FloatingOrb |
| Download GridBackground + IntelligenceField | ProductFrame (no importers) |

---

## E — Nodus source mapping

- Purchase: `vendor/nodus-agent-template/` (gitignored)  
- Product mirror: `components/marketing/nodus/*`  
- Preview SOT: https://ui.aceternity.com/templates/nodus-agent-template  
- Vendor `motion` → product `framer-motion`

---

## F — Animation-runtime audit

| Package | Status |
|---------|--------|
| framer-motion | Keep — default |
| @lottiefiles/dotlottie-react / lottie-web | Installed, **unused** — remove after confirm |
| gsap | Not present — add only for approved pinned narrative |
| three | Not present — avoid unless 1 signature WebGL |

---

## G–H — Gaps & primitives

Missing canonical: `GravitreHero`, `GravitreSection`, `GravitreProductStage/Frame`, semantic motion (`Flow`/`Trace`/`Pulse`/`Resolve`), unified `GravitreAmbientField`, illustration system, footer closing motif.

Existing to extend: Nodus `Hero`/`CTA`/`Footer`/`Container`/`DivideX`/`MarketingPageHero`/`MarketingRails`.

---

## I–L — Opportunities

- **SVG:** agent network, workflow path, connector hub, governance gate, GIBE TRACE, outcome resolve  
- **GSAP:** one pilot sticky CONNECT→LEARN on Technology/Workflows  
- **dotLottie:** only custom Gravitre assets if adopted  
- **WebGL:** keep auth; max +1 site-wide (GIBE brain)

---

## M–O — External sources

- **21st / Aceternity:** research + restyle into tokens; never paste stock looks  
- **Nucleo:** replace Lucide on marketing interiors; keep vendor logos for integrations

---

## P–S — Prototypes (specified, not built)

| ID | Prototype | Success |
|----|-----------|---------|
| P | Footer redesign | Feels final, Nodus-calm |
| Q | `/features/technology` full upgrade | Distinct story, same language |
| R | Shared motion wrappers | Semantic motions, not fade-up |
| S | Mobile of P+Q | Fewer layers; SSR copy intact |

---

## T — Performance estimate

Qualitative only (**bundle KB NOT RUN**). Risks: wide FM surface, unused Lottie deps, auth WebGL RAF, orphan pre-Nodus modules. Target: delete orphans; lazy GSAP/Lottie; WebGL ≤2.

---

## U — Phases (gated)

0. **This audit** — DONE  
1. Shared tokens + section + motion library  
2. **Footer pilot**  
3. **Inner page pilot** (`/features/technology` recommended)  
4. P0→P1→P2 rollout  
5. reduced-motion · SSR · Playwright goldens · bundle check  

---

## Site story

`CONNECT → UNDERSTAND → COORDINATE → ACT → VERIFY → LEARN`  
Each page owns one stage; visuals differ in content, not design language.

---

## Acceptance criteria (from brief) — status

| # | Criterion | Now |
|---|-----------|-----|
| 1 | Home + inner same system | **PARTIAL** |
| 2 | Footer intentional | **PARTIAL** |
| 3 | Not stock catalogue | **PARTIAL** (marketplace/docs/roadmap drift) |
| 4 | Motion consistent | **NO** |
| 5 | Nodus recognizable | **YES** on home/chrome |
| 6–15 | Graphics/CTA/Nucleo/perf/a11y/SEO | **GATED** until Phase 1–5 |

---

## STOP FOR CESAR APPROVAL

Approve before any production marketing implementation:

1. Phase 1 shared system spine  
2. Footer pilot scope (P)  
3. Inner pilot page choice: **Technology** (recommended) vs Features-as-Agents vs Workflows  
4. Whether auth pages may drop full marketing footer  
5. Whether GSAP / custom Lottie / extra WebGL are in budget for Phase 3  

**No invented prices, logos, testimonials, or TRAINED badges in marketing graphics.**

---

## Pilot shipped (2026-09-08) — after approval

Cesar approved the gate. Implemented Phase 1–3 pilot (no GSAP/Lottie/extra WebGL; auth footer unchanged pending separate decision):

1. **Tokens** — `--g-marketing-*`, motion aliases, `--g-graphic-*` in `globals.css`
2. **Primitives** — `components/marketing/system/` (`GravitreReveal`/`Flow`/`Trace`/`Pulse`/`Resolve`, `GravitreSection`, `FooterClosingField`, `GibeTraceVisual`)
3. **Footer** — denser Product / Enterprise / Resources / Company / Legal + calm TRACE closing field + site-story line
4. **Technology** — Lucide orbit replaced with GIBE TRACE SVG + Nucleo pills; legacy intelligence/governance content retained

Still gated: auth chrome slim, GSAP narratives, Lottie, site-wide P1/P2 rollout, Playwright goldens.

---

## P1 shipped (2026-09-09) — after Cesar “move to P1”

Extended System 4.0 across all audit P1 routes (no GSAP/Lottie/extra WebGL; auth footer unchanged):

1. **Shared visuals** — `StageTraceVisual` (+ page stage constants), `ConnectorHubVisual`, `ConvergeNodesVisual`, `SignalFieldVisual`
2. **Pages** — `/features/extension`, `/features/marketplace`, `/about`, `/contact`, `/security`, `/docs`, `/docs/faq`, `/docs/integrations`, `/api`, `/download`
3. **Scaffold cleanup (authorized by no-invented-surfaces rule while touching these pages)** — stripped marketplace `$49`/`$29` prices; removed API Starter/Growth/Enterprise invented req/min tiers; download retired parallel IntelligenceField/Grid/floating Lucide dual-hero

Still gated: auth chrome slim, GSAP, custom Lottie, P2 routes, Playwright goldens.

---

## P2 shipped (2026-09-09) — after Cesar “move to p3”

Audit has no priority P3; next remaining rollout tier was **P2**. Extended System 4.0 (framer only, no GSAP):

1. **Stage constants** — careers / blog / changelog / roadmap / guides / support TRACE spines
2. **Pages** — `/careers`, `/blog`, `/blog/[slug]`, `/changelog`, `/guides`, `/roadmap`, `/support`, `/privacy`, `/terms`, `/forgot-password`, `/docs/[...slug]` motion, `/docs/api/swagger`
3. **Scaffold cleanup** — stripped fake roadmap votes/progress, changelog metrics, support view counts, swagger `600 req/min`, guides YouTube/trial theater; forgot-password success labeled as demo reset

Still gated: auth footer slim, GSAP/Lottie, P0 inner upgrades (`/pricing`, `/features` distinct story), Playwright goldens.

---

## Open items closed (2026-09-09) — after Cesar “complete open items”

1. **P0** — `/pricing` Plan→Role→Outcome TRACE (PLAN_CATALOG dollars unchanged); `/features` Coordinate→Act→Approve→Resolve TRACE (home-clone sections removed)
2. **Auth footer slim** — `/login`, `/get-started`, `/forgot-password` use `Footer variant="slim"` via path-aware `MarketingChrome`
3. **Lottie** — removed unused `@lottiefiles/dotlottie-react` and `lottie-web` (never imported). **GSAP** remains intentionally out — roadmap sticky already uses framer; no pinned GSAP narrative budgeted
4. **Playwright goldens** — `e2e/marketing-system-smoke.spec.ts` DOM smoke (not pixel diffs) + `pnpm test:marketing-smoke`

Gate complete for Marketing System 4.0 rollout phases 1–4 + phase-5 smoke. Optional later: GSAP sticky narrative, visual screenshot baselines for marketing if motion is frozen.

---

## GSAP + marketing visual goldens (2026-09-09) — Cesar “do this now”

1. **GSAP pinned sticky** — `GsapSiteStorySticky` (ScrollTrigger pin) on `/roadmap` Connect→Learn; reduced-motion → static grid (post-mount to avoid SSR hydration mismatch). Dependency: `gsap` in `apps/web`.
2. **Screenshot baselines** — `e2e/visual/marketing-system-fidelity.spec.ts` with `prefers-reduced-motion` + CSS animation freeze; first-viewport shots for home/pricing/features/technology/security/roadmap @ 1440/1280/390. Artifacts under `e2e/visual/marketing-system-fidelity.spec.ts-snapshots/*-chromium-win32.png`. Refresh: `pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/marketing-system-fidelity.spec.ts --update-snapshots`.

**Evidence:** `pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/marketing-system-fidelity.spec.ts --update-snapshots` → **18 passed** (3.5m) on 2026-09-09 — baselines written for all 6 surfaces × 3 viewports.

No new prices/claims.

