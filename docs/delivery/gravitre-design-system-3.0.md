# GRAVITRE DESIGN SYSTEM 3.0

**Status:** Phase 1 foundations (2026-09-05)  
**Direction:** Light-first · Hybrid A+B marketing · Geist sans display  
**Code:** `apps/web/app/globals.css` (`--g-*`) · `apps/web/lib/design-system.ts`  
**Prior:** UI 3.0 research + Phase 0.5 concept boards  

Live marketing remains Pass 3 B2 **void** until Phase 3 consumes these tokens on a daylight canvas.

---

## 1. Brand north star

Warm mineral white canvas · Graphite system · Violet intelligence · Emerald action/truth · Cyan signal · Amber approval · Red critical.

Feel: cool-geek, calm, precise, premium — not generic AI neon.

---

## 2. Semantic color (OKLCH)

| Role | Token | Light intent | Use |
|------|-------|--------------|-----|
| Canvas | `--g-canvas` | `oklch(~0.985 0.006 110)` | Page ground |
| Graphite | `--g-text-primary` | `oklch(~0.22 0.018 165)` | Display / body |
| Intelligence | `--g-intelligence` | `oklch(~0.52 0.16 290)` | AI / GIBE / thinking |
| Action / Truth | `--g-emerald` | maps `--primary` | CTA / verified / healthy |
| Signal | `--g-signal` | `oklch(~0.55 0.11 220)` | Connectivity / transfer |
| Approval | `--g-approval` | amber, human gate | Pending approval only |
| Critical | `--g-danger` | maps `--destructive` | Failure |
| Success | `--g-success` | maps `--success` | Non-emerald success where needed |

Soft / surface / bright variants exist for intelligence, emerald, approval, signal.

**Rule:** Violet and emerald are semantic, not decorative wallpaper.

---

## 3. Surfaces + material

| Token | Role |
|-------|------|
| `--g-surface-1` … `--g-surface-3` | Panel ladder |
| `--g-surface-elevated` | Floated product stage |
| `--g-surface-active` | Intelligence-tinted selection |
| `--g-material-panel` | Mineral gradient fill |
| `--g-highlight-top` | Directional top edge light |
| `--g-shadow-subtle` → `--g-shadow-product` | Contact elevation (not neon glow) |
| `--g-border-subtle` → `--g-border-strong` | Fine graphite edges |

Material = mineral white + fine translucent edges + soft contact shadows + thin graphite detail.

---

## 4. Typography

**Font:** Geist (`--font-sans`) / Geist Mono for code.  
**Marketing display:** Sans only (Phase 0.5 mock serif rejected).

| Ladder | CSS var | App `TYPE` / `TYPE_MARKETING` |
|--------|---------|-------------------------------|
| DISPLAY | `--g-type-display` | `TYPE_MARKETING.display` |
| H1 | `--g-type-h1` | `TYPE_MARKETING.h1` |
| H2 | `--g-type-h2` | `TYPE_MARKETING.h2` |
| H3 | `--g-type-h3` | `TYPE.sectionTitle` |
| TITLE | — | `TYPE.cardTitle` |
| BODY | `--g-type-body` | `TYPE.body` |
| BODY SM | `--g-type-body-sm` | `TYPE.meta` |
| LABEL | `--g-type-label` | `TYPE.eyebrow` |
| METRIC | `--g-type-metric` | `TYPE.metricValue` |
| CODE / DATA | mono | (primitives) |
| CAPTION | `--g-type-caption` | `TYPE.meta` |

App hub surfaces keep existing `TYPE.*` density; marketing uses `TYPE_MARKETING` in Phase 3+.

---

## 5. Radius + spacing

| Role | CSS | TS `RADIUS` |
|------|-----|-------------|
| Control (pills) | `--g-radius-control` | `control` |
| Field | `--g-radius-field` | `field` |
| Tile | `--g-radius-tile` | `tile` |
| Card | `--g-radius-card` | `card` |
| Panel / stage | `--g-radius-panel` | `panel` |

Space scale: `--g-space-1` (4px) … `--g-space-8` (64px). Prefer semantic layout over ad-hoc magic numbers in new UI 3.0 work.

---

## 6. Motion grammar

| Concept | Purpose | Duration token | Ease | Reduced motion |
|---------|---------|----------------|------|----------------|
| FLOW | Information moving | `--g-motion-flow` | `--g-ease-signal` | Opacity only / static |
| PULSE | Intelligence active | `--g-motion-pulse` | `--g-ease-intelligence` | Static violet chip |
| WAVE | Voice / audio | `--g-motion-wave` | spring-damped | Static bars |
| TRACE | Execution progress | `--g-motion-trace` | `--g-ease-standard` | Step labels only |
| RESOLVE | Successful completion | `--g-motion-resolve` | `--g-ease-resolve` | Instant check |
| TRANSFER | Context/tool handoff | `--g-motion-transfer` | `--g-ease-signal` | Instant state |
| FOCUS | Attention move | `--g-motion-focus` | `--g-ease-intelligence` | Instant outline |

TS: `MOTION_CONCEPT` in `design-system.ts`.  
`ORBIT` retained for compat — **do not use in new UI 3.0 work**.

Marketing motion density > app. App prefers micro/state only.

---

## 7. Hybrid A+B marketing composition contract (Phase 3)

1. **Hero frame (A):** Layered real Gravitre product surfaces (Chat / Agents / Approvals / Connectors) on mineral canvas — product-as-hero.
2. **In-stage story (B):** Quiet UI → Intent → Tool (cyan Transfer) → Approval (amber) → Verified (emerald Resolve). No fake ROI.
3. **GIBE sections (C):** Topology / contour Intelligence Canvas language — not default grid; not the sole hero.
4. **CTAs:** Emerald primary; graphite secondary.
5. **Atmosphere:** Near-empty mineral + optional soft Lamp/Spotlight — no neon field as primary identity.

---

## 8. Cross-platform

| Surface | Token share | Variation |
|---------|-------------|-----------|
| Web app | Full `--g-*` + `TYPE` / `STATUS` | Low motion density |
| Marketing | `--g-*` + `TYPE_MARKETING` | Higher motion; daylight at Phase 3 |
| Desktop | Same tokens | Higher density panels |
| Mobile | Same semantics | Task-first; reduced FX |
| Extension | Same semantics | Micro-environment states |

Canonical visuals (Orb / Wave / Trace / Pulse / Resolve) share one implementation; platform wrappers only when required.

### Shared primitives (Phase 2)

| Primitive | Module |
|-----------|--------|
| `ProductStage` | `components/gravitre/visual/product-stage.tsx` |
| `StatusChip` | `…/status-chip.tsx` |
| `PulseDot` | `…/pulse-dot.tsx` |
| `TracePath` | `…/trace-path.tsx` |
| `ResolveMark` | `…/resolve-mark.tsx` |

Import from `@/components/gravitre/visual`.

---

## 9. Accessibility

- Contrast AA on mineral + emerald CTAs.
- Status never color-only (icon + text).
- Honour `prefers-reduced-motion` for all grammar concepts.
- Focus rings via `INTERACTION` / ring tokens.
- Voice always has text alternative.

---

## 10. Non-goals (standing)

No invented prices, TRAINED badges, Enable entitlement toggles, or fake live ROI — see `.cursor/rules/no-invented-customer-surfaces.mdc`.
