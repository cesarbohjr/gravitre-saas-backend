# Gravitre Product Visual System 3.0 Plus

**Status:** AUTHORIZED to start — Cesar 2026-09-20 · prototype → P-1 grammar on real TRACE; not broad production visual rollout  
**Date:** 2026-09-20  
**Builds on:** `GRAVITRE_PRODUCT_VISUAL_SYSTEM_2.0.md`, Nodus inheritance, Reset 2.0 tokens

---

## Philosophy

**Reset 1.0:** Minimum interface for maximum capability.  
**Reset 2.0:** Minimum interface ≠ minimum design.  
**3.0 Plus:** Make the intelligence **visible**.

Gravitre should feel advanced because:
- The interface knows what you are working on  
- Relationships and execution are visible  
- Motion explains state  
- Complexity appears only when needed  
- The product is **calm when idle, active when working**

**Not because of:** gradients, glow, sparkles, or card grids.

---

## Nodus inheritance (restraint)

Nodus provides: typography discipline, surface polish, sidebar rhythm (`--np-*`), compact ops density.  
Gravitre adds: topology, signal, trace, intelligence field, agent coordination visuals.

---

## Typography 3.0

### Current state (audit)

- **UI face:** Inter Display (`globals.css`, `fonts/inter-display/`)  
- **Mono:** DM Mono for code/trace  
- **Roles:** `TYPE.*` in `design-system.ts` — pageTitle, eyebrow, metricValue, etc.  
- **Problem:** Similar weights/grays on titles + metadata → **generic SaaS flatness**

### Proposed roles (explicit — prototype before global change)

| Role | Use | Direction |
|------|-----|-----------|
| Product title | Marketing only | Display tracking tight |
| Page title | Hub H1 | Semibold, primary text |
| Section title | In-page groups | Medium, secondary contrast |
| Object title | Row/inspector focus | Semibold, single line |
| Body | Prose | 14–15px operational |
| Operational body | Tables, queues | Slightly tighter line-height |
| Label | Form labels | 12px medium |
| Eyebrow | Hub section kicker | 11px uppercase, wide tracking (keep) |
| Metadata | Timestamps, ids | Muted, mono optional |
| Status | Pills (sparse) | Caption weight |
| Metric | KPI values | Tabular nums, larger scale |
| Numeric | Tables | `font-variant-numeric: tabular-nums` |
| Code / trace | Execution ids, spans | DM Mono selective |
| Nav | Sidebar | 13–14px, medium when active |

**Action:** Prototype type scale on Intelligence + Activity before global CSS change.

---

## Grid & spacing

### Current

- `--np-page-pad`, `--np-kpi-gap`, content often max-width floating  
- **Issue:** Large vertical gaps between header / KPI / table — accidental dead space

### 3.0 rules (draft)

| Region | Rule |
|--------|------|
| Hub header | Single band; no duplicate description blocks |
| KPI strip | Optional; max 4 metrics; omit when queue is primary |
| Main work | Lock to 12-col grid at ≥1280 |
| Inspector | Fixed width token (e.g. 380 / 420) |
| Graph canvas | Minimum height token; mobile → focused node mode |

---

## Canvas & surfaces (Depth System 3.0)

| Level | Token direction | Use |
|-------|-----------------|-----|
| Canvas | `--g-canvas` subtle mineral tint | App background — not pure #fff everywhere |
| Inline region | Low contrast band | Filters, subnav |
| Work surface | `--g-surface-1` white/elevated | Tables, graphs, composer |
| Selected surface | `--g-surface-active` | Inspector, selected row |
| Floating | Shadow + blur | AI workspace, command palette, popovers |
| Overlay | Modal / sheet | Mobile inspector |

**Borders:** Hairlines for structure; reduce box-around-everything.  
**Shadows:** Only floating/selected — not every KPI card.

---

## Color 3.0 (semantic scarcity)

Extend existing `--g-*` axes (do not rainbow):

| Axis | Meaning | Existing token |
|------|---------|----------------|
| Green / emerald | Brand, verified execution | `--g-brand`, `--g-emerald` |
| Violet | Intelligence, inference, learning | `--g-intelligence` |
| Cyan | Signal, connection, retrieval | `--g-signal` |
| Amber | Waiting, approval, uncertainty | `--g-approval` |
| Red | Failure, destructive | `--destructive` |
| Neutrals | Structure | `--g-text-*`, `--g-border-*` |

**Rule:** Most UI neutral; semantic color = system state, not decoration.

---

## Visual topology language

| Concept | Visual treatment |
|---------|------------------|
| Entity | Node (icon + label) |
| Edge | Relationship / dependency |
| Signal | Directed transfer (origin → destination) |
| Trace | Stage chain with failure pin |
| Flow | Workflow/agent path |
| Cluster | Department / ecosystem grouping |
| State | Color + motion (not pill alone) |
| Outcome | Terminal node resolution |
| Evidence | Attachment on trace stage |

---

## Signal primitive (Gravitre-native)

**Not:** glowing particles or random dots.

**Characteristics:** direction, origin, destination, state, confidence, resolution.

**Use selectively:** workflows, connectors, agents, intelligence, activity, GIBE learning return.

**Code seed:** extend `components/gravitre/visual/` (alongside `trace-path.tsx`, `pulse-dot.tsx`).

---

## Trace primitive

**Canonical stages (draft):** INTENT → PLAN → AGENT → TOOL → ACTION → RESULT → VERIFICATION → OUTCOME

**Surfaces:** Activity, Runs, Performance, Workflow builder overlay, Governance.

**Rule:** No invented timings — real telemetry only (Reset 2.0 binding).

---

## Intelligence Field (signature surface)

**Problem:** Intelligence hub reads as quiet columns in bordered boxes.

**Direction:** One shared intelligence topology; lens transforms state:
- KNOWS → entities + facts  
- LEARNS → strengthening edges  
- PREDICTS → inferred signals  
- ACTS → agent/workflow highlights  
- IMPROVES → feedback into graph  

**Not:** five decorative equal cards.

**Prototype gate:** 3 concepts in harness before any prod swap.

---

## Page introduction variants (anti-template)

Replace one-size **icon tile + eyebrow + title + description + divider** with job-based intros:

| Job | Intro pattern |
|-----|---------------|
| Command surface | Composer-forward (AI) |
| Workspace | Context + selection |
| Operations | Queue title + filters only |
| Graph | Canvas-first, minimal chrome |
| Queue | Count + primary action |
| Table | Title + toolbar inline |
| Discovery | Editorial hero (marketplace only) |
| Document | Settings rows |
| Trace | Outcome headline + stage rail |

Keep `GravitrePageHeader` as **one implementation** with variants — not 50 copies.

---

## Nucleo 3.0 pass

- Audit icons **in context** (size, weight, neighbor type)  
- Service logos = vendor logos (unchanged)  
- Expand semantic map only where meaning unclear  
- Sidebar: `sidebar-nucleo.tsx` resolution path  

---

## Motion (see INTERACTION_SYSTEM_3.0.md)

- Keep Framer Motion as primary engine  
- GSAP: marketing sequences only  
- R3F: only if spatial graph truly benefits  
- Enforce `MOTION` / `--g-duration-*` — no random literals  

---

## Responsive (390–1728)

| Breakpoint | Strategy |
|------------|----------|
| 390–430 | Bottom sheet inspector; graph → path explorer |
| 768 | Collapsed nav; stacked toolbar |
| 1024+ | Two-pane inspector |
| 1280+ | Full grid + optional topology panel |
| 1728 | Use width for graph/context — not empty margin |

---

## Accessibility

- Contrast on new canvas tints — verify WCAG  
- Topology: shape + label, not color-only  
- `prefers-reduced-motion`: static trace, no required animation  
- Focus rings on all command surfaces  

---

## Performance guardrails

- No WebGL on settings/billing  
- Graph lazy-load; cap node count on mobile  
- LCP: hero intros defer non-critical motion  
- Track bundle impact of new primitives  

---

## Quality bars (from program prompt)

Reject if it looks like: generic React admin, shadcn demo, Aceternity demo, Figma community dashboard, Nodus logo swap, AI-generated card grid.

Accept if: understandable in 5 seconds, operable quickly, movement explains state, feels like **Gravitre** without logo.

---

## Component plans

| Plan | Direction |
|------|-----------|
| Reuse | `GravitrePageHeader` variants, `GravitreTableShell`, trace primitives, Command OS shells |
| Remove | Orphan `PageHeader`, redundant KPI wraps, card-grid source tiles |
| Custom | Signal, Trace stage rail, Intelligence Field lens, Contextual Ask chip |

---

**Next step:** Prototype signature surfaces in harness — **STOP for Cesar** before production slice.
