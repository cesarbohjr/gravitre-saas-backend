# Gravitre 3.0 — Design Research Reference Library

**Purpose:** Capture principles and patterns from external products — not copy visual styles.  
**Date:** 2026-09-20  
**Status:** Research for 3.0 Plus planning only — no production implementation authorized.

---

## How to use this library

For each reference: extract **problem solved**, **what works**, **what Gravitre can learn**, **what Gravitre must not copy**.

---

## AI workspace & agent activity

| Source | Product / screen | Problem solved | What works | What does not | Learn for Gravitre | Do not copy |
|--------|------------------|----------------|------------|---------------|-------------------|-------------|
| Public UX writing | ChatGPT | Conversation simplicity | Single thread, calm composer, no chrome | Hides execution/governance | Persistent conversation spine; calm default | Generic bubble transcript forever |
| Public UX | Perplexity | Answer + source relationship | Citations adjacent to claims | Weak ops/governance | Source/evidence adjacency in AI replies | Search-only positioning |
| Industry reports | Manus / agent UIs | Agent activity + artifacts | Activity feed, artifact panel | Often demo-grade governance | Work surface when artifact exists; quiet when not | Fake autonomy badges |
| Internal harness | Gravitre `/dev/ai-workspace-preview` | Command OS exploration | Morph, work canvas, inspector gate | Mock data only | **Binding concepts already selected (Reset 2.0 B)** | Second runtime |

---

## Operational density & command

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| [Linear UI refresh](https://linear.app/now/behind-the-latest-design-refresh) | Linear | Dense ops without overwhelm | Receding chrome, softer borders, icon reduction, alignment discipline | Sidebar dims after arrival; content takes focus | Linear's issue-centric IA |
| [Linear redesign part II](https://linear.app/now/how-we-redesigned-the-linear-ui) | Linear | Hierarchy in navigation | Compact tabs, aligned sidebar micro-grid | — | Their project/issue ontology |
| Practitioner guide | Linear patterns | Keyboard-first speed | Cmd+K, mnemonic shortcuts, hover detail | — | 13px body as mandatory |
| Internal | Raycast (pattern) | Command-first modes | Predictable mode switching, palette as spine | Extend `command-palette.tsx` | macOS-only assumptions |

---

## Tables, settings, billing ops

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Public design | Stripe Dashboard | Operational tables + detail | Row hierarchy, detail drill, status restraint | Premium table = alignment + numerics | Stripe's payment visual language |
| Public design | Supabase Dashboard | Technical nav + data surfaces | Clear env/project context, SQL-adjacent density | Infrastructure framing for Sources | Supabase green/black brand |
| Internal | Gravitre `GravitreTableShell` | Hub table consistency | Shared bordered shell, `--np-shadow` | Evolve to Table 3.0 (sticky, numeric alignment) | Card replacement for all lists |

---

## CRM / structured work + embedded AI

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Public product | Attio | AI in structured records | Contextual AI on objects, not global widget | Selection → Ask pattern matches Phase 5 | CRM record layout |
| Internal | Gravitre contextual Ask | Hub summon + selection publish | `AskGravitreSummonButton`, `setSelectedEntity` | Unify to one contextual affordance pattern | Duplicate Ask on every toolbar |

---

## Intelligence, graphs, observability

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Public UX | Datadog / Sentry (pattern) | Execution observability | Trace timeline, failure stage pin | Activity → **execution story** with TRACE primitive | Vendor-specific chrome |
| Internal | Gravitre Relationships | Graph + evidence | Graph default, inspector on selection | Extend to **Intelligence Field** (one topology, many lenses) | Five equal decorative cards |
| Internal | `trace-path.tsx` | Path visualization primitive | Reusable trace SVG/motion | Standardize across Activity, Runs, Workflows | Invented timings without telemetry |

---

## Marketplace & discovery

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Pattern libraries | App store / SaaS marketplaces | Discovery density | Featured + catalog hybrid, rich metadata | Marketplace = **premium discovery objects** | Fake prices / Enable toggles (forbidden) |
| Internal | Gravitre marketplace split | Discovery ≠ installed ops | `assets` tiles vs `installed` list | Installed must not look like marketing cards | Oversized empty tile padding |

---

## Design systems & composition

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Public | Vercel / Geist | Grid, typography, contrast discipline | Restrained neutrals, strong type roles | Canvas + elevated work surfaces | Vercel developer-marketing aesthetic on ops pages |
| Licensed | Nodus template (internal) | SaaS admin foundation | `--np-*` layout rhythm, sidebar rail | **Nodus = restraint + polish** | Template page-template repetition |
| Libraries | shadcn / Aceternity / 21st.dev | Component velocity | Accessible primitives, patterns | Normalize into Gravitre tokens | Import demo components wholesale |
| Internal | `GRAVITRE_PRODUCT_VISUAL_SYSTEM_2.0.md` | Token SOT | `--g-intelligence`, `--g-signal`, etc. | Extend to 3.0 Plus semantics | Restart from zero |

---

## Motion & spatial UI

| Source | Product | Problem solved | What works | Learn | Do not copy |
|--------|---------|----------------|------------|-------|-------------|
| Internal | `GRAVITRE_MOTION_SYSTEM.md` | State vocabulary | EXPAND, FOCUS, TRACE, RESOLVE | Motion **inside work**, not page transitions | Random framer durations |
| Marketing only | GSAP site stories | Narrative scroll | Sequenced storytelling | Keep GSAP on marketing; not ops tables | Marketing motion on settings |
| Pattern | Figma / FigJam | Topology diagrams | Nodes, edges, states | **Visual topology language** for Gravitre | Decorative particle backgrounds |

---

## Research gaps (need Cesar / live sessions)

- Authenticated gravitre.app journey recordings at 390–1728  
- REFERO / Mobbin flow captures for approval queues and integration management (manual)  
- Figma Community pattern boards for **execution trace** and **knowledge graph** (manual)  

---

## Competitive principle summary (for 3.0 Plus)

| Principle | Primary references |
|-----------|-------------------|
| Calm chrome, active content | Linear, Vercel |
| Command as simplifier | Raycast, Linear |
| Tables can be premium | Stripe, Linear |
| AI embedded in object context | Attio, Perplexity (sources) |
| Trace explains failure | Sentry/Datadog patterns |
| Discovery ≠ operations | Marketplace best practice |
| Restraint + precision | Nodus + Nucleo (internal) |
| Intelligence visible, not decorative | **Gravitre-native** (topology, signal, trace) |
