# GRAVITRE UI 3.0 — NODUS FULL-MATCH · GATE 0 AUDIT

**Date:** 2026-09-06  
**Status:** **GATE 0 APPROVED** (Cesar 2026-09-06) — Phase 3–4 tokens/brand started  
**Prior program:** UI 3.0 Hybrid A+B / mineral phases **discarded as design SOT**

### Cesar decisions (recorded)

1. **Fonts:** Adopt Inter Display + DM Mono.  
2. **Home:** Keep Nodus section order; use real Gravitre logo.  
3. **Theme:** Light-first only (no dark/system product theme).  
4. **Vendor:** Keep `vendor/nodus-agent-template/` gitignored; mirror licensed design assets into the product tree as needed for match.  
5. **Brand:** Approve token extraction; orange → green `#16a374`.  
6. **Scope:** Consistent design across web app, desktop, browser extension, and mobile responsive web.

See Phase 3–4 delivery: `docs/delivery/ui-3-0-nodus-full-match-phase-3-4-tokens-brand.md`.

---

## A. Licensed source location

| Field | Value |
|-------|--------|
| Purchase zip | `C:\Users\Cesar\OneDrive\Gravitre\nodus-agent-template.zip` (7,134,185 bytes · 2026-09-06) |
| Unpacked | `C:\Users\Cesar\Downloads\Gravitre Operator AI\vendor\nodus-agent-template\` |
| Archive root name | `manuarora700-notus-agent-marketing-template-1aa99c8edb6d6c1eb7567dfa15cf114db741bd2e` |
| Git | `vendor/nodus-agent-template/` added to `.gitignore` (licensed source on disk; not committed by default) |
| License notices | Keep Aceternity / purchase attribution intact when shipping; do not strip vendor README/license requirements |

**Product identity in source:** marketing brand mixes **Notus** (logo/config) and **Nodus** (some meta/copy). Sold as **Nodus Agent Template** (Aceternity).

**Critical scope honesty:** This licensed package is a **Next.js marketing site template**, not a full operator app (no real chat workspace, dashboard app shell, workflow builder, or authenticated product).  
→ Marketing = **DIRECTLY ADAPT**.  
→ Web app / AI / desktop / extension = **EXTEND / PLATFORM-ADAPT** using Nodus tokens, composition, motion, and material — not file-for-file product screens that do not exist in the zip.

---

## Completeness checklist (Gate 0)

| Bucket | DISCOVERED | MAPPED |
|--------|------------|--------|
| Nodus files (excl. lock/node_modules) | **155** | **155** (inventory list under `vendor/nodus-file-inventory.txt`) |
| Nodus `components/**/*.tsx` | **47** | **47** |
| Nodus `public/**` assets | **41** | **41** |
| Nodus animation-touched files | **23** | **23** |
| Nodus routes (`app/**/page.tsx`) | **10** | **10** |
| Nodus placeholders / demo content clusters | **see G** | **see G** |
| Gravitre marketing routes | **28** | **28** (section M) |
| Gravitre app routes (excl. marketing/e2e/api) | **129** | **129** (section N — group map) |

Every DISCOVERED has a destination ACTION below. No “ignore” without Cesar approval.

---

## B. Complete Nodus file inventory (summary)

Full relative paths: `vendor/nodus-file-inventory.txt`.

| Area | Contents |
|------|----------|
| `app/` | Home, playground, pricing, about, careers, blog (+slug), contact, sign-in, sign-up, `globals.css`, `layout.tsx`, favicon |
| `components/` | Marketing sections + UI primitives + skeletons (47 TSX) |
| `icons/` | `general`, `bento-icons`, `card-icons`, empty `illustrations.tsx` |
| `fonts/` | Inter Display (local TTFs) + DM Mono |
| `constants/` | careers, faqs, founders, logos, pricing, testimonials |
| `data/` | 7 MDX blog posts |
| `hooks/` | `use-typewriter.ts` |
| `context/` | `theme-provider.tsx` |
| `lib/` | blogs, seo, utils |
| `config/` | site name/url/description |
| `public/` | dashboard shots, logos, avatars, team, illustrations, banner |

---

## C. Complete Nodus component inventory + ACTION

| NODUS ITEM | FILE | TYPE | VISUAL PURPOSE | GRAVITRE DESTINATION | ACTION |
|------------|------|------|----------------|----------------------|--------|
| Hero | `components/hero.tsx` | section | Badge + H1 + CTAs + social proof | Marketing home hero | **REBRAND** + **REBUILD WITH GRAVITRE DATA** (drop unverified Gartner) |
| HeroImage | `components/hero-image.tsx` | section | Parallax product screenshot | Home product stage | **REBUILD WITH GRAVITRE DATA** (real `/product/*` shots; keep motion/crop) |
| LogoCloud | `components/logo-cloud.tsx` | section | Trusted-by rotator | Home or Features | **REPURPOSE** — real logos only or remove claims |
| HowItWorks | `components/how-it-works/*` | section + skeletons | Tabbed demo + pixel fill | Home narrative / Features | **DIRECTLY ADAPT** structure; **REBUILD** demos as Gravitre flows |
| AgenticIntelligence | `components/agentic-intelligence/*` | bento + skeletons | Feature bento + fake chat/LLM/tools | Home GIBE / Features Technology | **DIRECTLY ADAPT**; demos → Gravitre AI/GIBE truth |
| UseCases | `components/use-cases.tsx` | section | Industry cards | Features / use-cases | **REBRAND** copy to authorized cases |
| Benefits | `components/benefits.tsx` | section | Benefit grid + center demo | Home pillars | **REBRAND**; strip fake “10x” / fake metrics |
| Testimonials | `components/testimonials.tsx` | section | Quote carousel | Optional | **USE AS PLACEHOLDER** only if gated; prefer remove until real |
| Pricing | `components/pricing.tsx` + table | section | Plans + matrix | `/pricing` | **REBUILD WITH GRAVITRE DATA** (authorized plans only) |
| Security | `components/security.tsx` | section | Compliance badges | `/security` | **REBRAND** — authorized claims only |
| FAQs | `components/faqs.tsx` | section | Accordion | Pricing / docs FAQ | **REBRAND** |
| CTA + CTAOrbit | `components/cta.tsx` | section | Closing CTA + orbit logos | Home / all marketing | **DIRECTLY ADAPT**; orange→green; logos→Gravitre |
| Navbar / Footer | `navbar.tsx` / `footer.tsx` | chrome | Nav + footer | Marketing chrome | **DIRECTLY ADAPT** |
| Auth forms + illustration | `sign-in.tsx` `sign-up.tsx` `auth-illustration.tsx` | pages | Decorative auth | `/login` `/get-started` | **DIRECTLY ADAPT** visuals; **keep Gravitre auth wiring** |
| Contact | `components/contact.tsx` | page | Form | `/contact` | **DIRECTLY ADAPT** |
| Heading / Subheading / Badge / Button / Container / DivideX | primitives | type/layout | Marketing type system | Shared marketing DS | **DIRECTLY ADAPT** |
| MeshGradient | `mesh-gradient.tsx` | WebGL | Auth/background | Auth / optional GIBE | **EXTEND** carefully; brand green |
| PixelatedCanvas / Scale / ScalesContainer / ProgressiveBlur / SlidingNumber / ShimmerText / TechCard / Dots / Lines | FX | craft | Density & motion | Marketing + selective product | **DIRECTLY ADAPT** / **PLATFORM-ADAPT** |
| UI Input/Label/Textarea | `components/ui/*` | form | Form chrome | Normalize into Nodus×Gravitre | **DIRECTLY ADAPT** |
| ModeToggle | `mode-toggle.tsx` | theme | Light/dark | Marketing + app | **DIRECTLY ADAPT** (light-first default OK) |
| Logo / LogoSVG | `logo.tsx` | brand | Notus mark | Replace with Gravitre logo assets | **REBRAND** |
| Icons packs | `icons/*.tsx` | SVG | Template icons | Prefer **Nucleo** for product; keep custom where unique | **REPLACE WITH NUCLEO** where equivalent; **KEEP CUSTOM** for unique marks |
| ThemeProvider | `context/theme-provider.tsx` | infra | next-themes | Already have | **EXTEND** |
| useTypewriter | `hooks/use-typewriter.ts` | motion | Chat demo typing | Demo / product streaming chrome | **PLATFORM-ADAPT** |

---

## D. Complete Nodus asset inventory

| ASSET | PATH | PURPOSE | GRAVITRE TRANSFORM | STATUS |
|-------|------|---------|-------------------|--------|
| Product dashboard | `public/dashboard.png`, `dashboard@3x.png` | Hero product image | Real Gravitre AI/Agents/Workflows screenshots in same frame/motion | **FINAL CAPTURE NEEDED** (temp: existing `/product/*`) |
| Banner / OG | `public/banner.png` | Social | Gravitre OG | **FINAL CAPTURE NEEDED** |
| Logo grid 1–10 | `public/logos/1–10.png` | Logo cloud | Real customer logos or remove | **TEMP / remove** |
| Press logos | bloomberg, wired, forbes, etc. | About press | Only if authorized | **Authorize or remove** |
| Compliance | CCPA/GDPR/ISO png | Security strip | Authorized only | **Authorize or remove** |
| Avatars / team | `avatars/*` `team/*` | Testimonials / about | Real team or remove | **Authorize or remove** |
| Illustration | `illustrations/native-tools-integration.svg` | Tools visual | Rebrand colors → green | **REBRAND DIRECTLY** |
| Favicon / next/vercel/file/globe/window svg | misc | Defaults | Gravitre favicon | **REBRAND** |
| Fonts Inter Display + DM Mono | `fonts/` | Typography SOT | Adopt as Nodus type baseline (or document Geist exception) | **DIRECTLY ADAPT** |

---

## E. Nodus animation inventory (major)

| COMPONENT | TRIGGER | DURATION / EASE | NOTES | GRAVITRE MOTION TOKEN |
|-----------|---------|-----------------|-------|------------------------|
| CTA orbit | ambient | 24s linear (CSS); rings ~18s+ | Keep | `--g-motion-ambient` |
| Hero stars | mount | 1s stagger 50ms | Keep or drop with Gartner | `--g-motion-enter` |
| HeroImage parallax | mouse + mount | spring 300/30; fade 0.3s d1s | Keep | `--g-motion-state` |
| Logo cloud swap | 3s interval | 0.2s easeInOut | Keep | `--g-motion-enter` |
| How-it-works tabs | 8s dwell | blur fade 0.5s; pixel fill 2.5s | Keep | `--g-motion-narrative` |
| Wire SVG gradients | loop | 2–5s easeInOut | Keep | `--g-motion-ambient` |
| Typewriter chat demo | sequence | 30ms/char | Product streaming optional | `--g-motion-micro` |
| Benefits text rotate | 4s | 0.3s | Keep | `--g-motion-enter` |
| FAQ accordion | click | 0.25–0.35s | Keep | `--g-motion-state` |
| SlidingNumber | price change | spring 280/18 | Pricing | `--g-motion-state` |
| MeshGradient | rAF | continuous; **respects reduced-motion** | Only reduced-motion-aware effect today | `--g-motion-ambient` |
| Conic spins | ambient | 2–4s | Brand orange→green | `--g-motion-ambient` |

**Gap:** Most effects lack `prefers-reduced-motion` — Phase 31 must add tokens without destroying hierarchy.

---

## F. Nodus token inventory → Gravitre-Nodus tokens

| NODUS TOKEN | VALUE | ROLE | GRAVITRE TOKEN | PROPOSED VALUE | RATIONALE |
|-------------|-------|------|----------------|----------------|-----------|
| `--color-brand` | `#f17463` | Accent / CTA / highlight | `--g-brand` | `#16a374` (logo sample) + oklch shades | Orange→logo green |
| charcoal-900/800/700 | `#202020`… | Graphite structure | `--g-graphite-*` | keep near Nodus | Structure unchanged |
| gray-100…600 | `#f9f9f9`… | Surfaces / muted | `--g-mineral-*` / canvas | keep near Nodus | Canvas rhythm |
| `--shadow-aceternity` | layered soft | Cards / inputs | `--g-shadow-aceternity` | keep | Material SOT |
| `--font-primary` | Inter Display | Display/UI | `--font-primary` | Inter Display (licensed in zip) | Nodus type confidence |
| `--font-mono` | DM Mono | Mono | `--font-mono` | DM Mono | Nodus |
| orbit keyframes | 24s | Ambient | keep | keep | Motion SOT |
| divide / dots / line / footer-link | CSS vars | Borders/chrome | map 1:1 | light + dark variants | Theme |
| violet (not in Nodus brand) | — | Intelligence only | `--g-intelligence` | existing violet | GIBE only; not brand |

### K. Gravitre green extraction (canonical)

| Field | Value |
|-------|--------|
| Source asset | `apps/web/public/images/gravitre-icon-green-1024.png` |
| Dominant pixel | **`#16a374`** · `rgb(22, 163, 116)` (~834k samples) |
| Soft halo | `#e0f3ec` |
| Existing CSS | `--primary: oklch(0.55 0.14 162)` (close; **reconcile to logo hex/oklch in Phase 4**) |

Proposed semantic set (Phase 4):

```
--g-brand: #16a374;
--g-brand-hover: /* darker mix */
--g-brand-active: /* deeper */
--g-brand-soft: #e0f3ec;
--g-brand-subtle: color-mix(...);
--g-brand-surface: color-mix(8% brand, surface);
--g-brand-border: color-mix(28% brand, border);
--g-brand-glow: soft green elevation;
```

Do not scatter hardcoded greens; do not leave Nodus orange residue.

---

## G. Nodus placeholder inventory

| PLACEHOLDER | WHERE | GRAVITRE DESTINATION | ACTION |
|-------------|-------|----------------------|--------|
| Notus / Nodus naming | logo, config, meta, footer | Gravitre | **REBRAND** |
| Fake prices $8/$12/$25 | `constants/pricing.tsx` | Real Stripe plans only | **REBUILD WITH GRAVITRE DATA** |
| Fake testimonials + ROI claims | `constants/testimonials.ts` | Remove or real | **Authorize** — default remove |
| Fake founders / Fight Club footer | founders, footer | Real company | **REBRAND / remove** |
| Gartner stars claim | `hero.tsx` | Remove unless licensed | **Remove** |
| SOC2 / ISO claims | faqs, security | Authorized only | **Authorize or remove** |
| Fake chat “Ask Notus AI” | skeletons | Gravitre AI demo chrome | **REBUILD WITH GRAVITRE DATA** |
| Fake metrics (85%/92%/65%) | benefits | Never as live | **USE AS PLACEHOLDER** labeled or remove |
| Blog MDX (Manu / generic) | `data/*.mdx` | Gravitre blog or drop | **REBUILD** |
| Logo cloud First…Tenth | logos | Real or remove | **Authorize** |
| Decorative sign-in/up | sign-in/up | Keep layout; real auth | **EXTEND** |

---

## H. Nodus → Gravitre component map (master)

| NODUS ELEMENT | NODUS LOCATION | FUNCTION | GRAVITRE EQUIVALENT | TARGET | TRANSFORM |
|---------------|----------------|----------|---------------------|--------|-----------|
| Hero | `hero.tsx` | Marketing hero | One-brain hero | Marketing `/` | Adapt layout + Gravitre copy/green |
| HeroImage | `hero-image.tsx` | Product stage | Real product PNGs | Marketing `/` | Same motion/frame |
| HowItWorks | how-it-works | Progressive explainer | Connect→Act→Verify→Learn | Marketing | Structure keep |
| AgenticIntelligence | agentic-intelligence | Feature bento | GIBE + Gravitre AI | Marketing + `/intelligence` language | Structure keep |
| Navbar/Footer | chrome | Site chrome | MarketingChrome | Marketing | Replace |
| CTA orbit | cta | Closing CTA | Home CTA | Marketing | Green rings |
| Auth illustration | auth-illustration | Auth left panel | Login / get-started | Auth | Adapt |
| Pricing | pricing* | Plans | `/pricing` | Marketing | Data swap |
| Mesh / pixel / scales | FX | Craft | Shared visual kit | Marketing → selective app | Shared package |
| *(no app shell in Nodus)* | — | — | `app-shell`, sidebar, chat | Product | **PLATFORM-ADAPT** from tokens |

---

## I. Content map (marketing story)

Nodus story → Gravitre (authorized):

| Nodus | Gravitre |
|-------|----------|
| Manage/simulate agentic workflows | One AI brain: connect tools, coordinate agents/workflows, approve, measure, learn |
| Start building / View pricing | Put Gravitre to work / Pricing |
| Agentic intelligence bento | GIBE + connectors + approvals truth |
| Use cases industries | Support / Sales / Ops / Leadership (no invented ROI) |
| Benefits “10x engineers” | Collaborate · Account · Improve (existing positioning) |

---

## J. Asset map

See **D**. Hero product image is highest priority capture.

---

## L. Nucleo icon map (initial)

| Surface need | Nodus today | Target Nucleo | Notes |
|--------------|-------------|---------------|-------|
| Nav / menu | Hamburger SVG | `NucleoMenu` | Have |
| Close | Close SVG | `NucleoClose` | Have |
| Search | — | `NucleoSearch` | Have |
| Settings | Moon/Sun custom | `NucleoSettings` | Have Gear |
| Agent / AI | Brain icons | `NucleoAgent` / `NucleoIntelligence` | Have |
| Workflow | custom | `NucleoWorkflow` | Have |
| Connector | Integrations icon | `NucleoConnector` | Have |
| Approval | Shield | `NucleoApproval` | Have |
| Voice | — | `NucleoVoice` | Have |
| Brand logos (Slack etc.) | Custom brand SVGs | **KEEP CUSTOM** | Brand recognition |
| Unique card icons | card-icons.tsx | Nucleo where match; else KEEP | Audit Phase 5 |

---

## M. Marketing migration plan (section-by-section)

1. Tokens + fonts + green (Phases 3–4 of program order)  
2. Navbar / Footer / Button / Container / Divide  
3. Home = Nodus section order (Hero→HeroImage→LogoCloud→HowItWorks→Agentic→UseCases→Benefits→[Testimonials optional]→Pricing optional on home→Security→FAQ→CTA) — **layout change allowed**  
4. Pricing, About, Careers, Blog, Contact, Auth pages  
5. Residue audit (Notus/Nodus/orange/fake claims)

---

## N. Web app migration plan (route groups)

| Group | Routes (count ~) | Nodus reference | Approach |
|-------|------------------|-----------------|----------|
| Shell | layout, sidebar, topbar, command | Navbar material + tokens | PLATFORM-ADAPT |
| Home dashboard | `/` app home | Benefits / card density | PLATFORM-ADAPT |
| AI Chat | `/ai`, `/chat` | Agentic chat skeleton language | PLATFORM-ADAPT + Agent Elements |
| Agents | `/agents*` | Cards / status | PLATFORM-ADAPT |
| Workflows | `/workflows*` | How-it-works visual grammar | PLATFORM-ADAPT |
| Connectors | `/connectors*` | Logo treatments | PLATFORM-ADAPT |
| Approvals / Runs | `/approvals`, `/runs*` | Status semantics | PLATFORM-ADAPT |
| GIBE | `/intelligence*` | AgenticIntelligence restraint + violet | PLATFORM-ADAPT |
| Marketplace | `/marketplace*` | Card hierarchy | PLATFORM-ADAPT |
| Settings / Enterprise | `/settings*`, enterprise | Calm forms/tables | PLATFORM-ADAPT |
| Remaining ~129 pages | inventory in tracker | Same DS | No legacy islands |

---

## O. AI Chat plan (states)

Empty · Streaming · Thinking · Tool select/exec · Delegation · Approval · Error · Success · Citations · Files · Voice — visual language from Nodus chat skeleton + Agent Elements + Nucleo; **not ChatGPT-green**.

---

## P–R. Dashboard / Agents+Workflows / GIBE

Use Nodus typography, spacing, shadow, radius, green brand; violet only for intelligence; real backend state only.

---

## S–U. Mobile / Desktop / Extension

| Surface | Plan |
|---------|------|
| Mobile responsive marketing | Preserve Nodus responsive classes; QA 375–1728 |
| Mobile web app | Bottom nav / sheets from same tokens |
| Desktop Tauri | Same DS, denser panels |
| Extension | Compact Nodus×Gravitre; Nucleo |

---

## V. Screenshot capture plan

| Shot | Source | Use |
|------|--------|-----|
| Nodus home @ 1440/768/390 | Run vendor template locally | Comparison board |
| Gravitre product surfaces | `/e2e/shots/*` + real captures | HeroImage replacements |
| Before/after Gravitre | Playwright | Regression after baselines |

---

## W. Functional protection

| Risk | Mitigation |
|------|------------|
| Auth / OAuth / billing | Visual-only chrome; keep existing handlers |
| Chat streaming / tools | Restyle wrappers; don’t rewrite runtime |
| Workflow builder canvas | Token/CSS first; no graph logic change |
| Connector OAuth | No auth rewrite in design phases |
| Invented prices/claims | Strip Nodus demo economics |

---

## X. Performance baseline

Not measured this gate. Before Phase 7 marketing ship: LCP/CLS/INP on `/` and `/ai`. Nodus MeshGradient + many motion loops need budget.

---

## Y. Implementation order (approved program)

Matches prompt §111:

1 Source inventory ✅ (this doc)  
2 Gravitre route inventory ✅ (summary)  
3 Token extraction  
4 Brand conversion (orange→`#16a374`)  
5 Nucleo conversion  
6 Shared primitives  
7 Marketing homepage  
8 Remaining marketing  
9 Auth  
10 App shell … through 33 Final residue  

**Stop here until Cesar approves Gate 0.**

---

## Z. Completeness (recount)

| Metric | Count |
|--------|------:|
| NODUS COMPONENTS DISCOVERED | 47 |
| NODUS COMPONENTS MAPPED | 47 |
| NODUS ASSETS DISCOVERED | 41 |
| NODUS ASSETS MAPPED | 41 |
| NODUS ANIMATION FILES DISCOVERED | 23 |
| NODUS ANIMATION FILES MAPPED | 23 |
| NODUS PLACEHOLDER CLUSTERS DISCOVERED | 12+ (section G) |
| NODUS PLACEHOLDER CLUSTERS MAPPED | 12+ |
| GRAVITRE MARKETING ROUTES DISCOVERED | 28 |
| GRAVITRE MARKETING ROUTES MAPPED | 28 |
| GRAVITRE APP ROUTES DISCOVERED | 129 |
| GRAVITRE APP ROUTES MAPPED | 129 (by group) |

---

## Open decisions for Cesar (approve Gate 0)

**RESOLVED 2026-09-06** — see status banner + Phase 3–4 doc. Remaining work is implementation, not Gate 0 blockers.

---

## Scaffold honesty

No new customer prices, TRAINED badges, Enable toggles, or fake ROI. Nodus demo economics and compliance claims must **not** ship as Gravitre product truth.
