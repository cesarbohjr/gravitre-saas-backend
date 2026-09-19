# Creative Experience System — Pilot 2 Agent Orchestration

**Status:** APPROVED AND SHIPPED (SVG Task Decomposition Field on `/features/technology`)  
**Progress:** W.1–W.8 done · Pilot 2 production plan complete · next bible step = Pilot 3 Knowledge Fabric  
**Upstream:** Pilot 1 shipped (Relational Topology + Departments Converge). **Do not reopen Pilot 1.**  
**Bible:** [`docs/design/gravitre-creative-experience-system.md`](gravitre-creative-experience-system.md)  
**Foundation:** `apps/web/components/marketing/creative/`  
**Engine inventory (2026-09-19):** `three` / `@react-three/fiber` / `@react-three/drei` still **absent** from `apps/web/package.json` (W.7 confirmed).  
**Product grammar note:** [`gravitre-creative-product-ui-grammar.md`](gravitre-creative-product-ui-grammar.md) (W.8)  
**Perf evidence:** [`docs/delivery/pilot2-w7-lcp-inp.md`](../delivery/pilot2-w7-lcp-inp.md)

Illustrative request (not live):  
**“Find at-risk customers and prepare the right follow-up.”**

---

## A. Pilot 1 regression check

| Check | Result |
|-------|--------|
| Relational Topology core present | **PASS** — `intelligence-core.tsx` documents Relational Topology; no `conic-gradient` / `animate-spin` orb |
| Creative foundation intact | **PASS** — `creative/core/tokens.ts`, `performance-manager.ts`, `relational-topology.ts` |
| `/about` converge host | **PASS** — still `ConvergeNodesVisual` → department-network |
| Honesty labeling pattern | **PASS** — “illustrative… not live org telemetry” |
| Three.js still not installed | **PASS** — no Three/R3F deps |

Pilot 1 not redesigned in this deliverable.

---

## B. Existing primitive reuse matrix

| Primitive | Status | Pilot 2 use |
|-----------|--------|-------------|
| Signal Trace | Exists (dept-network packets + paths) | Intent → Core; Agent → tool; return paths |
| Intelligence Core / Relational Topology | Exists | UNDERSTAND / PLAN geometry change |
| Relationship Trace | Exists (active + learned edges) | Agent↔work; persist LEARN only if story supports |
| Agent Node | **Not yet a shared creative primitive** | **Must introduce** as functional work node (not avatar) |
| Evidence Mark | **Not yet a shared creative primitive** | **Must introduce** at VERIFY / outcome |
| CREATIVE_TOKENS / PerformanceManager | Exists | Reuse quality, pause, brand `#16a374` |
| System motion FLOW/TRACE/… | Exists | Enter kinds + ASSEMBLE/DELEGATE/VERIFY/COLLAPSE |
| Nucleo semantic | Exists | Role icons subordinate to story |

**Work Fragment:** Do **not** create yet. Represent plan pieces as typography + Signal Trace + Agent Node until a gap is proven in prototype.

---

## C. Orchestration product-truth boundaries

**Safe (illustrative):**
- Intent → plan → specialized capabilities → tool use → handoffs → verification → evidence → governed write pause → continue
- Parallel work paths
- Shared org context metaphor

**Must not imply:**
- Every request always decomposes this way
- Live multi-agent debate / shared live memory
- Autonomous unrestricted action
- Instant cross-system execution without connectors
- Automatic approval / policy rewriting
- Exact agent set (Research/Sales/…) as product inventory

**Label on surface:** “Illustrative orchestration — specialized capabilities, governed execution, and evidence. Not a live run.”

---

## D. Concept A — ORCHESTRATION FIELD

**Spatial model:** Radial field. Intent at left edge; Relational Topology at center; Agent Nodes on a ring; tools on outer rim; outcome at right.

```
[Intent] → [Topology Core] ←ring→ [Agents] ←outer→ [Tools]
                              ↓
                         [Outcome + Evidence]
```

| Pros | Cons |
|------|------|
| Instant “hub” readability | Easy to look like generic network / Pilot 1 echo |
| Parallelism as simultaneous ring activity | Outer logo/tool rim risks connector explosion |
| Strong FOCUS on center | Weak left→right narrative for mobile |

**Uniqueness risk:** HIGH if ring density rises — reads as constellation AI cliché.

---

## E. Concept B — TASK DECOMPOSITION FIELD (bible primary)

**Spatial model:** Ordered semantic columns (position = meaning).

```
LEFT          CENTER                    MID-RIGHT         RIGHT
Intent   →    Topology + Plan fragments → Agents + Tools → Verify / Outcome
              (ordered stack, not explosion)
```

```
Intent capsule
    ↓ UNDERSTAND (topology reorganizes)
Plan band: [Identify] [Analyze] [CRM] [Response] [Prepare] [Verify]
    ↓ DELEGATE (fragments travel to Agent Nodes below/beside)
Agent row: Research · Analysis · Support · Ops  (illustrative roles)
    ↓ ACT (traces to capability ports — capability words, not logo wall)
Parallel: path A + path B concurrent
    ↓ COORDINATE / VERIFY (Evidence Marks)
Outcome collapses to one result
```

| Pros | Cons |
|------|------|
| Matches approved Pilot 2 direction | Needs careful density control |
| Position has meaning; ordered decomposition | Column layout less “wow” than 3D |
| Parallelism readable as concurrent lanes | |
| Native SVG + DOM typography | |
| Maps cleanly to mobile vertical stack | |
| Evidence + approval insert without restarting | |

**Uniqueness:** HIGH if decomposition is ordered and Evidence/Approval are first-class — not a workflow builder clone.

---

## F. Concept C — EXECUTION LATTICE

**Spatial model:** Time × work grid. Rows = capabilities; columns = stages (Plan → Act → Verify → Resolve). Traces light cells; failures freeze a cell amber/red.

| Pros | Cons |
|------|------|
| Failure/approval states crystal clear | Can read as Gantt / workflow builder |
| Strong product-UI grammar later | Weaker “one intent” emotional read |
| Excellent reduced-motion static | Less distinctive vs Gravitre marketing |

**Uniqueness risk:** MEDIUM — useful as product Activity grammar; weaker as marketing signature.

---

## G. Recommended spatial concept

### **Concept B — Task Decomposition Field**

**Why Gravitre:** Shows coordinated intelligence (intent → specialized work → tools → verify → evidence), not “AI did something.”  
**Why understandable:** Left-to-right (desktop) / top-to-bottom (mobile) reading order.  
**Why distinct:** Ordered decomposition + Evidence Marks + governed WAITING — not orbs, particles, or avatar agents.  
**Why Nodus-compatible:** Mineral structure, restrained color, DOM typography primary.  
**Why scales:** Same grammar for Technology, Features, Activity product traces later (interaction grammar only — not wholesale marketing animation).

---

## H. SVG storyboard (beats 0–10)

| Beat | Visual | Motion kind |
|------|--------|-------------|
| 0 Quiet | Empty mineral field; dormant topology | — |
| 1 Intent | Request capsule left; Signal Trace → core | FLOW / TRACE |
| 2 Understand | Topology geometry changes (receiving→connecting) | REORGANIZE |
| 3 Plan | Ordered fragments appear under core (related to intent) | ASSEMBLE / SPLIT |
| 4 Delegate | Fragments travel to Agent Nodes; nodes activate | DELEGATE |
| 5 Tool access | Capability ports (CRM / Analytics / Comms) — words + Nucleo, not logo wall | TRACE |
| 6 Parallel | ≥2 concurrent traces | PROPAGATE |
| 7 Coordinate | Results return; dependency resolve | ABSORB |
| 8 Verify | Evidence Marks attach to results | VERIFY |
| 9 Outcome | Paths COLLAPSE into one outcome card | COLLAPSE / RESOLVE |
| 10 Learn | Optional: one Relationship Trace persists | LEARN (advisory only) |

---

## I. R3F justification or rejection

**Rejection for Pilot 2 production (recommended).**

| Claimed R3F benefit | Assessment |
|---------------------|------------|
| Depth-dependent relationships | Concept B’s columns already encode meaning without depth |
| Layered task decomposition | 2D ordered bands communicate better for comprehension |
| Camera-assisted focus | Risks sci-fi fly-through; conflicts with Nodus restraint |
| Dense relationship readability | Density is a design problem; 3D often hides it |

**Install Three/R3F/drei:** **No** for Pilot 2. Revisit only if SVG prototype fails uniqueness or parallel-path readability in Cesar review.

R3F remains a **storyboarded alternative** (Section J), not an implementation path until approved.

---

## J. SVG vs R3F bake-off matrix

Scores 1–5 (higher better). Concept B assumed for both.

| Criterion | SVG | R3F | Notes |
|-----------|-----|-----|-------|
| Semantic clarity | **5** | 3 | Columns > depth |
| Story comprehension | **5** | 3 | Reading order |
| Visual distinctiveness | **4** | 4 | R3F risk of cliché if misused |
| Gravitre identity | **5** | 3 | Topology + evidence |
| Motion quality | **4** | 4 | FM/GSAP sufficient |
| Responsiveness | **5** | 3 | |
| Mobile | **5** | 2 | Separate 3D mobile = high cost |
| Accessibility | **5** | 2 | DOM-first |
| Reduced motion | **5** | 3 | Static final model easy in SVG |
| Performance | **5** | 2 | No Three bundle |
| Maintainability | **5** | 2 | |
| SEO/DOM integration | **5** | 2 | |
| Implementation complexity | **4** | 2 | |
| Failure mode | **5** | 3 | Error boundary lighter |
| Nodus compatibility | **5** | 3 | |
| **TOTAL** | **72** | **41** | |

### Verdict: **SVG WINS**

Hybrid (DOM + SVG + tiny WebGL field): **not recommended** for Pilot 2 — no clear layer responsibility beyond SVG.

---

## K. Final storyboard (production intent after approval)

1. Quiet topology  
2. Intent capsule + cyan Signal Trace  
3. Topology → receiving/connecting  
4. Six ordered plan chips (illustrative)  
5. Four Agent Nodes activate with relevant chips only  
6. Capability ports (CRM / Signals / Messaging) — no logo explosion  
7. Two parallel ACT traces  
8. One path hits **WAITING** (amber) at governed write  
9. Approval continues same trace (no restart)  
10. VERIFY + Evidence Marks  
11. COLLAPSE to outcome  
12. Optional LEARN edge persists  

Alternate loop: tool failure freezes one branch; prior success + blocked dependent + error Evidence Mark; governed recovery caption.

---

## L. Desktop composition

```
+------------------------------------------------------------------+
|  Intent          Coordination field           Outcome            |
|  [request]  -->  [Topology]                   [Verified result]  |
|                  [plan chips ordered]         [Evidence ···]     |
|                  [Agent] [Agent] [Agent]                         |
|                  capability ports (words)                        |
|  caption / aria-live beat text                                   |
|  honesty footnote                                                |
+------------------------------------------------------------------+
```

Quiet Nodus section chrome around the field. Pointer: hover clarifies related work; not required for comprehension. Prefer **autonomous loop** with optional scroll-scrub later (GSAP ST) if Cesar prefers narrative control — default: loop like Pilot 1.

---

## M. Mobile composition (390+)

Do not shrink desktop.

```
Intent
  ↓
Topology (compact)
  ↓
Plan chips (wrap)
  ↓
Agent work (stacked)
  ↓
Tools (capability chips)
  ↓
Parallel shown as two grouped branches
  ↓
Verify + Evidence
  ↓
Outcome
```

---

## N. Reduced-motion composition

Show **final information model** immediately:
- Intent text  
- Plan list  
- Agent roles involved  
- Tools/capabilities  
- Verification + evidence bullets  
- Outcome  

Static emphasis (FOCUS opacity) only — no continuous motion.

---

## O. Approval state

- Trace reaches controlled write  
- Agent/capability node → **WAITING** (amber)  
- Motion on that path **stops**  
- Caption: “Needs approval before write.”  
- On approve (demo beat): **same** Signal Trace continues green → EXECUTE  

Governance = part of execution, not a separate product.

---

## P. Failure state

- One tool ACT fails at the failed stage  
- Prior path remains successful (green/mineral)  
- Failed node gets Evidence/error mark (NucleoError)  
- Dependent path dims (blocked)  
- Caption names stage; no full-scene red flood  

---

## Q. Evidence state

Evidence Mark = small mineral glyph + short label (“sources”, “run outcome”, “policy”) attached to specific result nodes — different stroke from execution Trace (violet/graphite vs green action).

Communicates: **AI did something + we can show why.**

---

## R. Nucleo mapping (illustrative roles)

| Role label | Nucleo (approx) | Avoid |
|------------|-----------------|-------|
| Research / identify | `NucleoSearch` | brain-for-all |
| Analysis | `NucleoIntelligence` (nodes) sparingly | sparkles |
| CRM / customer | existing customer-adjacent / connector | robot |
| Messaging | `NucleoChat` / send | magic wand |
| Verify | `NucleoSuccess` / `NucleoApproval` | |
| Failure | `NucleoError` | |
| Run / act | `NucleoRun` | |

Icons subordinate to structure.

---

## S. Motion mapping

| Beat | Kind |
|------|------|
| Intent travel | FLOW / TRACE |
| Topology change | REORGANIZE |
| Plan appear | ASSEMBLE / SPLIT |
| To agents | DELEGATE |
| Tool ACT | TRACE / PROPAGATE |
| Results home | ABSORB |
| Evidence | VERIFY |
| Outcome | COLLAPSE / RESOLVE |
| Persist | LEARN |

No constant float/orbit/pulse/particles.

---

## T. Performance estimate

| Item | Estimate |
|------|----------|
| Bundle delta (SVG Pilot 2) | Low — FM already present; no Three |
| Init | Comparable to Pilot 1 department-network |
| Runtime | Pause offscreen + `document.hidden` (reuse PerformanceManager) |
| If R3F later | Lazy dynamic import; +~150–250KB gzip class risk — measure before approve |

---

## U. Component architecture (post-approval)

```
apps/web/components/marketing/creative/
  core/          # existing tokens + performance
  primitives/
    relational-topology.ts   # existing
    agent-node.tsx           # NEW — functional work node
    evidence-mark.tsx        # NEW
    signal-trace.tsx         # extract/share from dept-network if needed
  scenes/
    agent-orchestration/     # NEW scene only after approval
      storyboard.ts
      orchestration-field.tsx  # SVG
      mobile.tsx
      reduced.tsx
```

Do **not** fork a second creative framework. Do **not** modify Pilot 1 department-network except shared primitive extractions if needed.

**Suggested surface after approval:** `/features` or technology subsection — not `/about` converge.

---

## V. Test plan

Widths: 390, 430, 768, 1024, 1280, 1440, 1728 — covered by `e2e/creative-pilot2-orchestration-widths.spec.ts`  

States: default, active, delegation, parallel, waiting approval, verification, failure, resolved, learned (optional), reduced-motion, offscreen, document.hidden  

Deterministic: `?creativeState=verify` (localhost / 127.0.0.1 only — ignored on public hosts)  

Unit: storyboard beat order; Evidence present at VERIFY; approval continues same path id; failure does not paint entire scene error — `apps/web/__tests__/marketing/creative-experience-system.test.ts`

---

## W. Production implementation plan (only after Cesar approval)

1. ✅ Extract/share Signal Trace if needed; add Agent Node + Evidence Mark primitives  
2. ✅ Implement SVG Task Decomposition Field scene + mobile + reduced  
3. ✅ Wire approval + failure alternate loops  
4. ✅ Mount on agreed marketing route behind Nodus section chrome  
5. ✅ Honesty footnote + a11y captions  
6. ✅ Vitest + Playwright widths + localhost `?creativeState=` freeze  
   - Unit: `apps/web/__tests__/marketing/creative-experience-system.test.ts`  
   - E2E: `e2e/creative-pilot2-orchestration-widths.spec.ts` (390–1728)  
7. ✅ Measure LCP/INP on `/features/technology`; confirm no Three  
   - Evidence: `docs/delivery/pilot2-w7-lcp-inp.md` + `docs/delivery/pilot2-technology-webvitals-summary.json`  
   - Desktop LCP 2.2 s PASS vs 3.3 s bar @ 2026-09-19T08:54:01Z; no Three in package.json/lock  
8. ✅ Document product-UI grammar extraction opportunities (Activity / Approvals) — no wholesale import  
   - `docs/design/gravitre-creative-product-ui-grammar.md`  

**R3F path:** closed unless Cesar rejects SVG verdict.

**Pilot 2 complete.** Next program step: bible **Pilot 3 Knowledge Fabric** (do not reopen Pilot 1/2 production unless Cesar reopens).

---

## Approval asks (Cesar) — CLOSED

1. ✅ **Concept B — Task Decomposition Field**  
2. ✅ **SVG wins** — Three/R3F not installed  
3. ✅ Illustrative request + honesty labeling  
4. ✅ Agent Node + Evidence Mark only new primitives  
5. ✅ Surface: `/features/technology` (Pilot 1 `/about` untouched)
