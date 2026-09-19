# Creative Experience System — Pilot 3 Knowledge Fabric

**Status:** SHIPPING — SVG Entity Convergence on `/features/technology`  
**Upstream:** Pilot 1 (`/about`) and Pilot 2 (Task Decomposition on Technology) **locked — do not reopen.**  
**Bible:** [`docs/design/gravitre-creative-experience-system.md`](gravitre-creative-experience-system.md) §O  
**Foundation:** `apps/web/components/marketing/creative/`  
**Engine:** SVG + DOM typography first. **No Three / R3F** unless SVG fails uniqueness or density in Cesar review (bible: R3F only if SVG fails).

Illustrative story (not live):  
Mentions of the same company arrive from different systems → **normalize** → **exact match converges** → evidence attaches.  
**Sarah** and **Sarah Smith** stay **separate** (not fuzzy person match).

---

## A. Product-truth boundaries

**Safe (illustrative):**
- Exact string match after normalization (trim / case / punctuation)
- Mentions converging into one resolved entity node
- Evidence that a match occurred
- Knowledge Fabric as **mention → identity** grammar — separate from org graph / department topology

**Must not imply:**
- Fuzzy `"Sarah"` ↔ `"Sarah Smith"` person matching
- Knowledge Fabric ≡ org graph ≡ live CRM sync
- Live customer data or realtime ER telemetry
- Certified / TRAINED / silent confidence

**Surface label:**  
“Illustrative entity convergence — exact and normalized mention match. Not fuzzy person matching. Not a live org graph.”

Memory Phase 1 product truth (engineering): opaque-alias vectors are **exact HMAC** of normalized mentions — marketing scene teaches that honesty without exposing crypto details.

---

## B. Spatial concept — Entity Convergence (bible Concept A)

```
LEFT (mentions)     CENTER (gate)           RIGHT (resolved)
[Acme Corp]  ──►    normalize + exact  ──►  [Entity: Acme Corp]
[acme corp.] ──►    match                  + Evidence Marks
[Sarah]      ···    (no merge) ·········   [Sarah] stays distinct
[Sarah Smith]····   (no merge) ·········   [Sarah Smith] stays distinct
```

**Deformable Lattice** (Core Concept B) deferred — not required for Pilot 3 signature.

---

## C. SVG vs R3F

| Criterion | SVG | R3F |
|-----------|-----|-----|
| Semantic clarity (match vs no-match) | **5** | 3 |
| Honesty of exact-only ER | **5** | 3 |
| Mobile / a11y / reduced-motion | **5** | 2 |
| Bundle / LCP risk | **5** | 2 |
| **Verdict** | **SVG WINS** | closed unless Cesar rejects |

---

## D. Storyboard (beats)

| Phase | Visual |
|-------|--------|
| quiet | Scattered mention chips; dormant fabric |
| receive | Mentions enter from left (Signal Trace metaphor) |
| normalize | Chips show normalized form under raw text |
| match | Exact pair converges to one entity node |
| reject_fuzzy | Sarah / Sarah Smith remain two nodes — caption honesty |
| evidence | Evidence Marks on resolved entity |
| persist | One Relationship Trace / fabric edge remains |
| distinct | Optional loop emphasis: KF ≠ org graph (caption) |

Deterministic freeze: `?kfState=match` (localhost only).

---

## E. Architecture

```
apps/web/components/marketing/creative/
  scenes/knowledge-fabric/
    storyboard.ts
    entity-convergence-field.tsx
```

Reuse: `CREATIVE_TOKENS`, `GravitreEvidenceMark`, PerformanceManager patterns (visibility + reduced motion).  
Do **not** modify Pilot 1 department-network or Pilot 2 orchestration except shared barrel export.

**Mount:** `/features/technology` — new section after Orchestration (not `/about`).

---

## F. Test plan

- Vitest: phase order; exact pair converges; fuzzy pair does not; localhost `kfState` gate
- Playwright widths 390–1728 + `kfState=match` / `reject_fuzzy`
- No Three in package.json

---

## G. Production checklist

1. ✅ Design + honesty boundaries (this doc)  
2. ✅ SVG Entity Convergence scene + reduced + mobile stack  
3. ✅ Mount on Technology + honesty footnote  
4. ✅ Vitest + Playwright (`creative-experience-system.test.ts`, `e2e/creative-pilot3-knowledge-fabric-widths.spec.ts`)  
5. ⬜ Optional: LCP spot-check after ship (do not block Pilot 3 if desktop LCP stays under prior bar)
