# Creative → Product UI grammar (Pilot 2 extraction note)

**Status:** Phase 12 first slice shipped — see [`gravitre-creative-phase12-product-ui-grammar.md`](gravitre-creative-phase12-product-ui-grammar.md). Still **no wholesale import** of marketing animation into product.  
**Source pilots:** Departments Converge (Pilot 1), Task Decomposition Field (Pilot 2).  
**Date:** 2026-09-19 · Phase 12: 2026-09-20

---

## What transfers

Marketing creative established **interaction grammar**, not a second design system:

| Creative primitive | Product surface candidate | Extract as |
|--------------------|---------------------------|------------|
| Signal Trace (origin → dest → state) | Activity timeline step edges; run inspector hops | Stroke + state colors; no continuous orbit |
| Agent Node (functional work node) | Activity “who worked” chips; Approvals actor row | Label + capability role; **not** avatar face |
| Evidence Mark | Approvals evidence strip; Activity verify row | Short label (“sources”, “run outcome”, “policy”) |
| WAITING (amber pause on same path) | Approvals queue item; governed write gate | Path continues after approve — **no restart** |
| Failure scoped to one branch | Activity failure row; dependent step dimmed | Prior success stays green; no full-scene red |
| Ordered plan chips | Activity plan / task breakdown (read-only) | Typography list; not workflow-builder chrome |
| Honesty caption pattern | Product empty/partial states | “Not live / illustrative” only where true |

---

## What must **not** transfer

- Marketing **autonomous loop** timing into product Activity (product = event-driven).
- Full SVG Task Decomposition Field as a product page chrome.
- Connector **logo walls** (keep capability words / Nucleo).
- Invented confidence, TRAINED badges, or live multi-agent debate metaphors.
- Three.js / R3F for Activity or Approvals (same Pilot 2 rejection unless a later bake-off wins).

---

## Activity hub — grammar only

Safe first slices (interaction language, existing layout):

1. **Step edge state** — pending / running / waiting / verified / failed using creative semantic colors (`#16a374`, amber, intelligence violet, error red).
2. **Evidence attach** — when a step has sources / run outcome, render `Evidence Mark`–class chip (shared primitive optional later).
3. **Waiting continues path** — approval CTA resumes the same run/path id (Pilot 2 `GOVERNED_WRITE_PATH_ID` lesson).

Do **not** replace Activity inspector with the marketing field scene.

---

## Approvals — grammar only

1. **WAITING** amber on the write under review.
2. Approve → same path id proceeds to EXECUTE / VERIFY (caption: governance is part of execution).
3. Evidence Marks for why the write was proposed (policy / sources) — product-truth only when data exists.

---

## Shared package path (later, gated)

If/when product adopts primitives, prefer import from:

`apps/web/components/marketing/creative/primitives/`

…or a thin `apps/web/components/gravitre/creative-grammar/` re-export — **after** a named product owner approves each surface. No drive-by mount on `/activity` or `/approvals`.

---

## Explicit non-goals

- Pilot 3 Knowledge Fabric productization (separate program).
- Replacing Nodus product chrome with marketing section stacks.
- Shipping placeholder prices / Enable toggles as grammar demos.
