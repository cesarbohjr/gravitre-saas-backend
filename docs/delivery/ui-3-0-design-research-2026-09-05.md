# GRAVITRE UI 3.0 — DESIGN RESEARCH (GATE 0)

**Date:** 2026-09-05  
**Status:** **APPROVED 2026-09-05** — research locked; Phase 0.5 concepts next (`docs/delivery/ui-3-0-phase-0.5-concepts.md`)  
**Canvas:** `gravitre-ui-3-0-design-research.canvas.tsx`  
**Benchmark:** Nodus Agent Template (Aceternity) — craft bar only, not a clone  
**Live Nodus preview:** https://notus-agent-marketing-template.vercel.app/  
**Live Gravitre:** https://gravitre.app/ (current = Design Pass 3 **B2 dark**; UI 3.0 supersedes to **light-first**)

## Access honesty

| Source | Access |
|--------|--------|
| Nodus live marketing template | **PUBLIC** (`notus-agent-marketing-template.vercel.app`) |
| Nodus on 21st / Aceternity product pages | **PUBLIC** preview chrome |
| Aceternity / 21st Pro source | **Not inspected / not purchased** |
| Gravitre production | Live homepage + repo architecture |
| Playwright | Present for e2e; **no** marketing golden `toHaveScreenshot` suite yet |
| GSAP / Three / Spline | **Not** in `apps/web` deps today |
| dotLottie | **Already** in `apps/web` (`@lottiefiles/dotlottie-react`) |

---

## 1. Nodus visual forensic report

### What makes Nodus feel like Nodus

1. **Typographic confidence** — huge, calm display type; one accent word (coral/red on “workflows”); no gradient-soup headlines.
2. **Product-as-hero** — light **product shell** (sidebar + metrics + table) sits *inside* a dark marketing void; the UI is the graphic.
3. **Restraint** — black void, white primary CTA, thin icons, generous blackspace; almost no particle/grid cliché in the hero frame.
4. **Section rhythm** — statement → product stage → feature mosaics → industries → benefits → social proof → pricing → FAQ → CTA. Adjacent sections don’t all look like “3 cards.”
5. **Micro-interaction density** — Motion for React tasteful hovers/reveals; motion answers “what is active,” not decoration.
6. **Dual-surface craft** — marketing is dark/editorial; embedded product mock is light/dense. That split is intentional and premium.

### Observed structure (live)

| Region | Observation |
|--------|-------------|
| Nav | Minimal logo mark · sparse links · white pill CTA · theme toggle |
| Hero | Coral eyebrow · large H1 · muted H2 · dual CTA · light social proof |
| Product stage | Large light dashboard: sidebar, ⌘K search, 4 KPI cards, workflow monitor table |
| How it works | Integration / multi-agent / sandbox narratives with UI fragments |
| Features | Mixed feature tiles (LLM selector, text→workflow, tools, auth, sync, SDK) |
| Use cases | Industry grid (DevOps, SalesOps, …) |
| Benefits | Engineer-speed claims with supporting visuals |
| Pricing / FAQ / Footer | Standard SaaS close; clean, not noisy |

### Motion map (observed / inferred from public preview)

| Motion | Character | Gravitre takeaway |
|--------|-----------|-------------------|
| Hero enter | Opacity + slight Y; ~400–700ms ease-out | Keep; pair with product stage rise |
| CTA hover | Soft scale / brightness | Emerald primary, not white clone |
| Product stage | Likely scroll opacity / parallax of light panel | Prefer sticky product story |
| Feature tiles | In-view stagger | Vary layouts; no identical card rows |
| Theme toggle | Instant class swap dark↔light | UI 3.0 is **light-first**; dark is secondary |

### Typography / spacing / surface (Nodus)

- **Type:** Bold sans display; clear weight ladder; long-line muted subheads.
- **Spacing:** Large hero vertical rhythm; product stage has dense internal padding vs sparse marketing margins.
- **Surface:** Marketing = flat near-black; product = warm white panels, hairline borders, soft contact shadow — **not** neon glass.
- **Background:** Hero void is mostly empty; sophistication comes from type + product, not FX.

### Responsive notes

- Public preview includes Desktop / Tablet / Mobile chrome on Aceternity.
- Live Notus at mobile width collapses nav to toggle; product stage stacks; still product-led.

### What NOT to copy

- Notus brand, coral accent system, pricing, copy, fake Gartner claim if present, layout 1:1.
- Dark-first marketing as Gravitre’s primary (UI 3.0 is light-first).
- Generic “agent SaaS” vocabulary without Gravitre accountability story.

---

## 2. Current Gravitre screenshot board (live)

**Evidence pointer:** Live capture `https://gravitre.app/` — Pass 3 B2 void: dark canvas, emerald CTAs, grid + Intelligence Field, “One AI brain…”, brain-flow diagram, progressive narrative.

### Strengths vs Nodus

| Gravitre better | Why |
|-----------------|-----|
| Differentiated messaging | One-brain / accountability story is stronger than “simulate workflows” |
| Product truth discipline | Real `/public/product` captures; illustrative demos labeled |
| Semantic color intent | Emerald action, violet intelligence already conceptualized |
| Governance / outcomes vocabulary | Missing from Nodus template narrative |

### Weaknesses vs Nodus craft

| Gap | Detail |
|-----|--------|
| Cliché atmosphere | Dot grid + glowing topology reads “AI template,” not engineered mineral light |
| Typographic confidence | Emerald gradient/glow CTAs + neon emerald type feel sci-fi vs Nodus calm white |
| Product stage | Brain diagram is conceptual; Nodus embeds a **believable product shell** as the hero graphic |
| Section rhythm | Narrative is strong but still many centered statement blocks; less editorial variety |
| Metadata bug | Document title = `Homepage Title` (placeholder) |
| Theme conflict | UI 3.0 wants light-first; live site is dark B2 |
| Motion grammar | Present but uneven; not documented Flow/Pulse/Trace/Resolve |
| Cross-platform DS | Marketing ≠ app shell materials; extension/desktop not unified |

---

## 3. Nodus vs Gravitre gap analysis (executive)

| Dimension | Nodus | Gravitre now | UI 3.0 target |
|-----------|-------|--------------|---------------|
| Theme | Dark marketing + light product mock | Dark marketing throughout | **Light-first** marketing + app |
| Hero graphic | Real UI stage | Diagram + screenshots | Product stage / living workflow |
| Atmosphere | Near-empty void | Grid + field glow | Mineral Intelligence Canvas (custom) |
| Type | Calm white + one accent | Emerald accent overload | Graphite display + violet/emerald semantic |
| Motion | Tasteful micro | Mixed density | Documented grammar; marketing > app |
| Icons | Thin consistent set | Mixed Lucide + Nucleo | **Nucleo canonical** |
| Craft score (est.) | 8.5–9 composition | 6–7 composition | ≥9 marketing / ≥8 product |

---

## 4. Reference library (25+)

Categorized. **Recreate / Adapt / Reject** = recommendation for Gravitre.

### Hero / background

| # | Name | Source | Cat | Verdict |
|---|------|--------|-----|---------|
| 1 | Nodus live product-stage hero | notus-agent-marketing-template.vercel.app | HERO | **ADAPT** craft, not brand |
| 2 | Agenforce marketing template | ui.aceternity.com | HERO | ADAPT layout discipline |
| 3 | Spotlight (Aceternity) | 21st id 989 | BG | ADAPT — soft light on mineral white |
| 4 | Background Beams | 21st id 1152 | BG | ADAPT carefully — risk of neon |
| 5 | Animated Beam | 21st id 919 | CONNECT | **ADAPT** for connector transfer |
| 6 | Border Beam | 21st id 1268 | MICRO | ADAPT for focus cards |
| 7 | Laser Focus shader | 21st id 16342 | BG | EVALUATE — light retoken or **REJECT** if sci-fi |
| 8 | Flow Field Background | 21st id 9962 | BG | ADAPT as topology — retoken mineral |
| 9 | Aether Flow | 21st id 6419 | SHADER | EVALUATE for GIBE only |
| 10 | Liquid Crystal Shader | 21st id 6832 | SHADER | **REJECT** default blobs |
| 11 | Ethereal Beams Hero | 21st id 4127 | HERO | REJECT as stock dark hero |
| 12 | Woven Light Hero | 21st id 5240 | HERO | EVALUATE / high GPU |
| 13 | Lamp | 21st id 24569 | LIGHT | ADAPT for light material edge |

### Product / agent / intelligence

| # | Name | Source | Cat | Verdict |
|---|------|--------|-----|---------|
| 14 | Thinking | 21st id 23592 | AGENT | **ADAPT** → Gravitre thinking states |
| 15 | Thinking Reasoning | 21st id 23578 | AGENT | ADAPT |
| 16 | AI Chain of Thought | 21st id 20075 | AGENT | ADAPT (honesty: no fake CoT claims) |
| 17 | AI Agent Pipeline | 21st id 20802 | WORKFLOW | ADAPT Trace grammar |
| 18 | Thinking Orbs | 21st id 21710 | VOICE | ADAPT into GravitreOrb — not stock |
| 19 | Agent Avatar | 21st id 23820 | AGENT | EVALUATE |
| 20 | AI Agent Processing States | 21st id 14940 | STATE | ADAPT semantics |

### Motion / scroll / craft techniques

| # | Technique | Source | Verdict |
|---|-----------|--------|---------|
| 21 | Shared layoutId transitions | Motion / Framer | **ADAPT** product↔marketing |
| 22 | useScroll + useTransform parallax | Motion | ADAPT product stage |
| 23 | AnimatePresence route/state | Motion | KEEP (already in stack) |
| 24 | ScrollTrigger pin + scrub | GSAP docs | EVALUATE marketing Phase 3 |
| 25 | SVG path draw / morph | GSAP / SVG | ADAPT Trace |
| 26 | Clip-path / mask reveals | CSS + Motion | ADAPT screenshot stages |
| 27 | Sticky product narrative | Editorial pattern | **ADAPT** homepage |

### Aceternity-class (names as craft patterns)

| # | Pattern | Use |
|---|---------|-----|
| 28 | Spotlight / Lamp / Tracing beam | Local light, not full-page neon |
| 29 | Text Generate / Typewriter | Use sparingly; prefer status Trace |
| 30 | Macbook / iPhone frames | Prefer Gravitre Product Stage over device chrome |
| 31 | Infinite moving cards | **REJECT** as default marquee cliché unless transformed |
| 32 | Bento grid | **REJECT** as default; allow rare asymmetric mosaic |

---

## 5. Stack gap report

| Tech | Decision | Why | Existing alternative |
|------|----------|-----|----------------------|
| **Playwright visual QA** | **NEEDED** | Golden screenshots for marketing/app; regression | Failure-only screenshots today |
| **dotLottie** | **KEEP / selective** | Already installed; good for empty/success/extension | SVG+Motion for most UI icons |
| **GSAP + ScrollTrigger** | **EVALUATE → likely Phase 3 marketing only** | Pinned product stories Nodus-level | Motion scroll can cover 70% |
| **Three / R3F** | **NOT YET** | High cost; only if GIBE needs real 3D topology | Canvas flow field / SVG |
| **Spline** | **NOT NEEDED initially** | Art-direction velocity ≠ required for light material system | v0 lab + SVG |
| **New shader packs** | **EVALUATE one** custom Intelligence Canvas | Avoid stock liquid/neon | CSS+SVG Field rewrite |
| **Nucleo** | **NEEDED expansion** | Canonical icons across surfaces | Partial Nucleo + Lucide mix now |

### Performance budget (proposed)

| Surface | Budget |
|---------|--------|
| Marketing LCP | ≤2.5s on mid desktop |
| Marketing JS | Prefer CSS/SVG/Motion; GSAP only if pinned stories ship |
| App INP | ≤200ms; motion density low |
| WebGL | Optional; must have static fallback; no hero WebGL by default |
| FPS ambient | ≥55 idle on marketing; pause offscreen |

---

## 6. Three homepage concepts (must differ)

### Concept A — Organizational Intelligence Stage

- **Hero:** Light mineral canvas; graphite display type; emerald CTA.
- **Graphic:** Real Gravitre product layers (Chat / Agents / Approvals / Connectors) composed as an operational stage — Nodus-like product-in-frame, Gravitre surfaces.
- **Motion:** Stage rises; connectors Trace between panels; status Resolve.
- **Differentiation:** Business OS, not “workflow simulator.”

### Concept B — Living Product

- **Hero:** Quiet real UI → executes a truthful Gravitre sequence (intent → tool → approval → verified).
- **Motion:** Cursor/status choreography; no fake $ ROI.
- **Background:** Near-empty mineral; light Lamp/Spotlight only.
- **Differentiation:** Behavior > metaphor.

### Concept C — Intelligence Canvas

- **Hero:** Custom Gravitre field (topology / refraction / contour — **not** default grid) morphs into product UI.
- **Tech:** Prefer Canvas/SVG; shader only if unique and light-friendly.
- **Risk:** Highest cliché risk — must pass “not AI template” test.

**Gate:** Do not pick a concept until Cesár reviews A/B/C mockups (Phase 0.5 after approval of this research).

---

## 7. Product / mobile / desktop / extension concepts (summary)

| Surface | Concept direction |
|---------|-------------------|
| **Web app** | Dense calm mineral shell; graphite type; violet intelligence chips; emerald verified; low motion; operational dashboard ≠ card grid |
| **Mobile** | Task → state → action; bottom sheets; reduced FX; thumb CTAs |
| **Desktop** | Native density; ⌘K; resizable panes; same tokens; not “website in a window” |
| **Extension** | Micro-environment: context → capture → agent → approval → status; Nucleo + Pulse/Resolve |

---

## 8. Design System 3.0 — token proposal (not implemented)

### Semantic roles

| Role | Hue intent | Use |
|------|------------|-----|
| Canvas | Warm mineral white `oklch(~0.985 0.006 110)` | Page ground |
| Graphite | Near-black text `oklch(~0.22 0.02 165)` | Display/body |
| Intelligence | Violet `oklch(~0.52 0.16 290)` | AI / GIBE / thinking |
| Action/Truth | Emerald (logo-saturated) | CTA / verified / healthy |
| Signal | Cyan `oklch(~0.55 0.11 220)` | Connectivity / transfer |
| Approval | Amber | Pending human gate |
| Critical | Red | Failure |

### Surfaces / depth

- Material: mineral white panels, fine translucent edges, soft contact shadows (not neon glow).
- Elevation ladder: subtle → surface → elevated → product-stage.
- Light tokens: directional top highlight + local spotlight (marketing only).

### Type ladder

DISPLAY · H1–H3 · Title · Body · Body SM · Label · Metric · Code · Data · Caption — Geist OK pending optical audit; weights must feel Nodus-confident on light.

### Motion grammar (canonical)

FLOW · PULSE · WAVE · TRACE · RESOLVE · TRANSFER · FOCUS — each with duration/easing/reduced-motion rules (to be documented in Phase 1).

---

## 9. Nucleo icon mapping (initial)

Map Nucleo to: Home, Agent, Workflow, Run, Connector, Approval, GIBE, Search, Audit, Marketplace, Governance, Voice (listen/think/speak), Success, Warning, Failure, Settings, Account.  
Tiers: 16 / 18 / 20 / 24 / 32.  
**Deprecate** ad-hoc Lucide on marketing/product chrome except approved exceptions.

---

## 10. Component architecture (direction)

| Existing | Action |
|----------|--------|
| MarketingChrome / Hero / Field | **REPLACE** under UI 3.0 light system |
| ProductFrame | **MODIFY** → Product Stage primitive |
| IntelligenceField | **REPLACE** atmosphere (no default grid) |
| FeatureCard row | **REPLACE** section compositions |
| ThemeProvider + ThemeToggle | **KEEP** — app light/dark; marketing light-first |
| GravitreOrb / Wave / Voice visualizers | **KEEP API**, restyle |
| shadcn primitives | **KEEP** as a11y infrastructure |
| ConnectorIcon | **KEEP**, Nucleo-adjacent consistency |

Shared primitives to introduce: `g-material`, `ProductStage`, `StatusChip`, `TracePath`, `PulseDot`, `ResolveMark`.

---

## 11. Motion architecture boundaries

| System | Responsibility |
|--------|----------------|
| CSS | Hover, focus rings, simple fades |
| SVG | Trace paths, icons, topology |
| Motion (framer-motion) | Product interaction, layoutId, presence |
| GSAP | Optional marketing scroll cinema only |
| dotLottie | Cross-platform branded empty/success only |
| WebGL/Spline | Optional GIBE/hero — gated |

---

## 12. Playwright visual QA architecture (proposed)

- Add `e2e/visual/` with `toHaveScreenshot()` for marketing home, pricing, app shell, agents, approvals (fixture org).
- Viewports: 1440×900, 768×1024, 390×844.
- Freeze animations (`prefers-reduced-motion` + settle waits) for goldens.
- Separate **reference gallery** (Nodus PNGs) for human side-by-side — not pixel-equality CI.
- Commit Gravitre goldens after Phase 3/4 acceptances.

---

## 13. Accessibility strategy

- Contrast AA on light mineral + emerald CTAs.
- Status never color-only (icon + text).
- Full `prefers-reduced-motion` for Pulse/Trace/Wave.
- Keyboard + focus rings on Product Stage demos.
- Voice always has text alternative.

---

## 14. Phased implementation (after approval)

| Phase | Scope |
|-------|-------|
| 0 | **This research** ← STOP |
| 0.5 | A/B/C homepage mockups + app shell mock (screenshots) |
| 1 | Tokens + foundations (light-first) |
| 2 | Shared primitives + Nucleo map |
| 3 | Marketing website |
| 4 | Web app shell |
| 5 | Core product surfaces |
| 6 | Mobile responsive |
| 7 | Desktop |
| 8 | Browser extension |
| 9 | Cross-platform consistency |
| 10 | Visual regression goldens |
| 11 | Perf + a11y |
| 12 | Final design QA (≥8 / marketing ≥9) |

Each phase: screenshot → compare → refine → accept. No big-bang CSS rewrite.

---

## 15. Explicit non-goals (Gate 0)

- No production code changes in this deliverable  
- No dependency installs  
- No homepage redesign yet  
- No Nodus asset/source copy  
- No invented prices / TRAINED / Enable / fake live ROI  

---

## Approval gate

**APPROVED** by Cesar (2026-09-05). Phase 0.5 concept boards delivered.

### Approved direction (2026-09-05)

- **Homepage concept:** Hybrid **A+B** (A product stage + B living execution; C for GIBE/intelligence sections only).
- **Type:** Sans display (Geist).
- **Phase 1:** Tokens + foundations only — do not flip live marketing void → daylight until Phase 3.
