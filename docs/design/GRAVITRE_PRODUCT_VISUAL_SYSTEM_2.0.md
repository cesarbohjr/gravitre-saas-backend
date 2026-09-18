# GRAVITRE PRODUCT VISUAL SYSTEM 2.0

**Program:** UX Reset 2.0 (planning). Extends Nodus + UI 3.0 tokens. **Does not invent prices, badges, or Enable toggles.**

**SOT for values:** `apps/web/app/globals.css`, `apps/web/lib/design-system.ts`.  
**Logo green:** `#16a374` from `gravitre-icon-green-1024.png` (commented in `globals.css`).

---

## Inheritance

Nodus remains visual foundation: Inter Display, charcoal type `#202020`, canvas white / `#f9f9f9` background, hairline `#eaedf1`, product header ~36px, sidebar 220px, radius 6/8/12px on product chrome.

Reset 1.0 added: object-first IA, one AI workspace, no card-first default.  
Reset 2.0 adds: **design intelligence inside simplicity** — composition, depth, motion, Nucleo, spatial models — without glow-as-futurism. The AI workspace is the **reference grammar** (type, space, surface, depth, border, radius, shadow, Nucleo, buttons, icon actions, inputs, composer, selection, focus, hover, loading, error, empty, execution, sources, artifacts, inspector, motion, responsive, reduced motion). Do not invent AI-only styling that cannot generalize.

**Effects:** one local treatment at a time (radial light **or** hairline highlight **or** floating blur — not all). Shadows mean float / overlay / drag / selection depth, not “this is a card.”

**Rails:** no permanently irrelevant rails. History: expanded/fullscreen, collapsible, hidden in compact. Inspector: only with selection. Execution: while relevant, then collapsible.

---

## Color

| Role | Token | Hex / value | Use |
| --- | --- | --- | --- |
| Brand / healthy execution | `--g-brand` / `--primary` | `#16a374` | Identity, success-adjacent, focus ring |
| Hover / active brand | `--g-brand-hover` / `--g-brand-active` | `#128a63` / `#0f7a58` | Controls |
| Soft brand | `--g-brand-soft` | `#e0f3ec` | Selected tint, never full-page fill |
| Intelligence / GIBE | `--g-intelligence` | `oklch(0.52 0.16 290)` | Reasoning, learning — product only |
| Connection / signal | `--g-signal` | `oklch(0.52 0.12 240)` | Retrieval, edges, data flow |
| Approval / wait | `--g-approval` | `oklch(0.72 0.14 75)` | Amber attention |
| Failure | `--g-danger` / `--destructive` | oklch destructive | Errors |
| Type | `--g-text-primary` | `#202020` | Body |
| Muted | `--g-text-muted` | `#8b8b8b` | Meta |

Do not paint the product green. Do not create a second palette. Marketing may stay more expressive; authenticated Gravitre stays this ladder.

---

## Typography

Use `TYPE` in `design-system.ts`. Operational pages: `pageTitle` is `text-xl` / `sm:text-2xl`, not marketing display. Prefer density over hero headers. AI responses stay readable body, not card chrome.

---

## Space

Nodus `--np-page-pad` 16px, `--np-kpi-gap` 12px, `--np-row-h` 36px. Reset 2.0: important objects get more space; secondary collapses. Do not add 200px page heroes.

---

## Surface / depth

| Level | Meaning | Token |
| --- | --- | --- |
| 0 | Application canvas | `--g-canvas` / `--g-background` |
| 1 | Functional region | Proximity + hairline, usually **no** shadow |
| 2 | Selected surface | `--g-surface-active`, `--g-border-active` |
| 3 | Floating workspace / popover | `--g-shadow-elevated` / `--elevation-3` |
| 4 | Modal / critical | `--g-shadow-product` / `--elevation-4` |

`--g-shadow-subtle`, `--g-shadow-surface`, `--g-shadow-elevated`, `--g-shadow-product` already exist. Map Reset 2.0 names:

| 2.0 name | Existing token |
| --- | --- |
| `--g-shadow-subtle` | same |
| `--g-shadow-raised` | `--g-shadow-surface` |
| `--g-shadow-floating` | `--g-shadow-elevated` |
| `--g-shadow-overlay` | `--g-shadow-product` |

No Material umbra. No glow on every card. `--shadow-aceternity` is Nodus marketing/product chrome — do not sprinkle on every table.

---

## Border

Hairline `--g-border-default`. Stronger only for selection, focus (`--ring` `#16a374`), error, drag, true section break.

---

## Radius

| Role | Token | Notes |
| --- | --- | --- |
| Control | `--g-radius-control` / `RADIUS.control` | Pills for buttons — **do not** pill tables |
| Field | `RADIUS.field` | Inputs are rectangles |
| Tile / card / panel | 8 / 12 / 16-ish | Hierarchy by size |

Reset 2.0: fewer capsules. Lists and tables stay rectangular.

---

## Layout vocabulary (choose per route)

WORKSPACE · CANVAS · LIST · TABLE · TIMELINE · GRAPH · FLOW · QUEUE · SPLIT VIEW · DOCUMENT · COMMAND SURFACE · INSPECTOR · DETAIL · METRIC STRIP · ACTIVITY STREAM.

Same design system. **Not** the same header + KPI cards + table on every page.

---

## Data visualization

Prefer the information as the interface: graph, flow, pipeline, queue, trace. Metrics as strip or annotation, not four identical stat cards (except Home widgets, which remain modular).

---

## Effects

See `GRAVITRE_MOTION_SYSTEM.md`. Futuristic = precision + response + connection, not neon.

---

## Responsive

Recompose, do not stack cards. Targets: 390, 430, 768, 1024, 1280, 1440, 1728. Desktop canvas → mobile list / sheet / focused object / compact AI.

---

## Accessibility

Keyboard, visible focus (`--ring`), contrast on charcoal/white, `prefers-reduced-motion`, named icon-only controls, 32/44px hits.

---

## Libraries (authority order)

1. Existing Gravitre / Nodus  
2. Nucleo Sharp  
3. Aceternity **normalized** (registry exists; no dump-in)  
4. 21st.dev / Agent Elements as **patterns**  
5. shadcn for a11y primitives  
6. Custom SVG / Canvas / existing graph engine  
7. GSAP / WebGL only where already justified  

Do not add another UI framework.
