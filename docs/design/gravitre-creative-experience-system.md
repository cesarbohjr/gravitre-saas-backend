# Gravitre Creative Experience System 1.0

**Status:** Approved direction (Cesar) — Pilot 1 = Departments Converge on `/about`  
**Gate:** Nodus restraint + Gravitre intelligence storytelling. No stock orbs / particle clouds as signature.

Brand green (exact): `#16a374` (`--brand` / `--g-brand`).

---

## A. Nodus source audit

| Item | Result |
|------|--------|
| Licensed source | **FOUND** — `vendor/nodus-agent-template/` (gitignored) |
| Inventory | `vendor/nodus-file-inventory.txt` |
| Product mirrors | `apps/web/components/marketing/nodus/*`, fonts, `apps/web/public/nodus/` |
| Authority | Gate 0 audit; `docs/design/GRAVITRE_UX_RESET_2.0.md` |

Nodus owns typography, spacing, rails, chrome. Creative layer is additive.

---

## B. Marketing route audit

Full `(marketing)` tree (~25 routes). Signature converge lives on **`/about`** via `ConvergeNodesVisual` → `department-network/`.

Home uses Nodus section stack; older `hero-brain-flow` / parallax leftovers are unwired.

---

## C–D. Animation + creative inventory

| Asset | Path | Role |
|-------|------|------|
| Semantic motion | `components/marketing/system/motion.tsx` | FLOW / TRACE / PULSE / RESOLVE / FOCUS |
| Department network | `system/department-network/*` | Pilot 1 host |
| Connector hub / signal field / GIBE TRACE / stage TRACE / footer field | `system/*` | Reuse grammar |
| GSAP sticky | `gsap-site-story-sticky.tsx` | `/roadmap` |
| Product orbs | `voice-presentation.tsx` | **Product UI only** — not marketing signature |

---

## E–I. Dependency + engine readiness

| Engine | Status |
|--------|--------|
| framer-motion | **Available** ^12.38 |
| gsap (+ ScrollTrigger) | **Available** ^3.15 |
| three / R3F / drei | **Not installed** — add only after Pilot 2/3 bake-off |
| Raw WebGL | `nodus/mesh-gradient.tsx` (auth) only |
| SVG / Canvas | Primary creative engines |
| Reduced motion | Global CSS + `MotionConfig` + per-scene |

---

## J. Performance baseline

Prefer SVG for relationship stories. Cap WebGL to ≤1–2 signature experiences. Viewport lifecycle before any R3F. Budgets: do not worsen marketing LCP; pause offscreen / `document.hidden`; DPR ≤1.5–2.

**Shared canvas decision:** multiple isolated canvases (not one persistent site WebGL).

---

## K. Creative design language

Feel: cool-geek, calm, precise, premium, alive — quiet Nodus UI around a living intelligence system.

### Five signature primitives only

1. **Signal Trace** — directional segmented capsule (origin → destination → state)
2. **Intelligence Core** — Relational Topology; geometry changes by state
3. **Relationship Trace** — appears when active; **persists after LEARN**
4. **Agent Node** — functional work node (not avatar)
5. **Evidence Mark** — attaches to outcome; never silent confidence

### Semantic colors

| Token role | Use |
|------------|-----|
| Green `#16a374` | Execution / resolve / Gravitre |
| Violet (`--g-intelligence`) | Reasoning / GIBE |
| Cyan / blue | Signal / transfer |
| Amber | Approval / waiting |
| Red | Failure / critical |
| Mineral white + graphite | Default structure |

---

## L. Signal system

- Not a glowing ball
- Capsule + path measure (`getPointAtLength`)
- Kinds: `signal` | `action` | `learn`
- Direction, origin, destination, state required

---

## M. Intelligence Core — three concepts → **A primary**

| Concept | Verdict |
|---------|---------|
| **A. Relational Topology** | **PRIMARY** — SVG nodes/edges reorganize per state |
| B. Deformable Lattice | Later (Knowledge Fabric) |
| C. Generative Field | Reject as primary (sci-fi / particles) |

### Core states (geometry must change)

`IDLE` → `RECEIVING` → `CONNECTING` → `REASONING` / `COORDINATING` → `VERIFYING` → `LEARNING` → idle with **+1 permanent relationship**

---

## N. Agent Orchestration — **B primary** (Pilot 2)

Task Decomposition Field (SVG first): request → plan fragments → agents → tools → verify → outcome. Spatial R3F only if bake-off wins.

---

## O. Knowledge Fabric — **A primary** (Pilot 3) — SHIPPED

Entity Convergence (exact/normalized ER — label honesty; not fuzzy person match).  
Production: SVG `EntityConvergenceField` on `/features/technology` — see [`gravitre-creative-pilot3-knowledge-fabric.md`](gravitre-creative-pilot3-knowledge-fabric.md). No Three/R3F.

---

## P–U. Storyboards

### Departments Converge (Pilot 1)

Isolated → Sales signal → Core receiving/connecting → Support joins → Finance/Ops branch → Outcomes return → **Learned permanent edge**.

Honesty: scripted metaphor for org-scoped shared context — not live telemetry.

### Governance

POLICY → RISK → APPROVAL → EXECUTE → EVIDENCE (gate opens; trail remains).

### GIBE

ACTION → OBSERVE → EVALUATE → RECOMMEND (advisory) → human Approve; preferred path retained.

### Connector Fabric

Capability ports (READ/WRITE/…) — not logo wall.

### Voice

Waveform → semantic structure → intent → context → action → response (no Siri orb).

### Outcomes

Traces collapse into positioning categories (revenue/retention/efficiency) — no invented metrics.

---

## V. Page experience map

| Route | Priority | Experience |
|-------|----------|------------|
| `/about` | **P0 Pilot** | Departments Converge v2 |
| `/features/technology` | P0 | GIBE TRACE + evidence honesty |
| `/` | P1 | Quiet Nodus; optional Living System prototype |
| Agents / workflows | P1 | Agent Orchestration |
| Connectors | P1 | Connector Fabric |
| `/security` | P2 | Governed Execution |
| Pricing / auth / legal | P3 | Quiet + shared signal accents |
| `/roadmap` | Keep | Align tokens |

Rhythm: quiet → signature → quiet → product proof → CTA.

---

## W. Technology matrix

| Experience | Engine | Fallback | Risk |
|------------|--------|----------|------|
| Departments Converge | SVG + FM (+ GSAP ST optional) | Static SVG | LOW |
| Agent Orchestration | SVG first; R3F if needed | SVG | MED |
| Knowledge Fabric | R3F only if SVG fails | Canvas/SVG | MED/HIGH |
| Governance / GIBE / Connectors | SVG + Motion/GSAP | Static | LOW |

---

## X. Component architecture

```
apps/web/components/marketing/creative/
  core/          # PerformanceManager, ProgressModel, tokens
  primitives/    # Signal, Trace, IntelligenceCore (topology)
  scenes/        # future pilots
  fallbacks/
```

Pilot 1 extends `system/department-network/` rather than forking a parallel converge.

---

## Y–AB. Performance / mobile / a11y / fallback

- Quality tiers: HIGH / MED / LOW / FALLBACK
- Mobile: simplified sequence (`department-network-mobile`) — same story, different execution
- Touch: no hover-required meaning
- `prefers-reduced-motion`: final composition + captions
- DOM captions + `aria-live` for beats
- Error boundary: scene failure must not break marketing page
- Pointer-events: SVG overlay must not block CTAs

---

## AC. Testing

Playwright widths 390–1728; reduced-motion; optional `?creativeState=` for deterministic frames (dev).

---

## AD–AE. Phases + pilot

1. Design bible (this doc)  
2. Tokens + performance stubs  
3. Signal + Trace + Relational Topology Core  
4. **Pilot 1: `/about` Departments Converge**  
5. Pilot 2 Agent Orchestration bake-off  
6. Pilot 3 Knowledge Fabric — **SHIPPED**  
7. **Remaining experiences (in progress)** → hero eval → footer continuity → hardening  
   - ✅ Connector Fabric on `/docs/integrations`  
   - ✅ Governed Execution on `/security` ([`gravitre-creative-governed-execution.md`](gravitre-creative-governed-execution.md))  
   - Next: hero eval → footer continuity → hardening 

**First production pilot = Departments Converge on `/about`.** No Three.js until Pilot 2/3 justification.

---

## AF–AJ. Risks / deps / reuse / retire

**Risks:** product-truth overclaim; WebGL tax; CTA blocking; Core reverting to orb.

**Add later only:** `three`, `@react-three/fiber`, `@react-three/drei`.

**Reuse:** department-network story engine, motion kinds, brand tokens.

**Retire:** ring-spin core; unused home floating-orb / hero-brain leftovers as creative signatures.

---

## Product-truth (non-negotiable)

Do not imply live: finished one-brain composition; realtime multi-agent debate; GIBE auto policy rewrite; KF ≡ org graph ≡ fuzzy ER; Certified/TRAINED; voice as fully proven duplex.

Safe: org-scoped shared context; governed writes; Observe→Learn→Recommend→Approve; agent handoffs; separate KF vs org graph.

---

## AK. Implementation note

Pilot 1 ships Relational Topology Intelligence Core + permanent learned edges + honesty caption on `/about`. Prototypes live in-tree as the production path (upgrade existing network), not a disposable demo route.
