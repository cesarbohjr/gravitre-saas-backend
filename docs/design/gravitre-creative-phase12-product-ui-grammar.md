# Creative Experience System — Phase 12: Product UI grammar (first slice)

**Status:** SHIPPING  
**Upstream:** CES 1.0 closed at Phase 11. Cesar reopen = this phase.  
**Source:** [`gravitre-creative-product-ui-grammar.md`](gravitre-creative-product-ui-grammar.md)  
**Package:** `apps/web/components/gravitre/creative-grammar/`

## Product-truth

**Safe:** WAITING amber on the same path; EvidenceChip labels from real step/approval data; spine stream color by status.  
**Must not:** Wholesale marketing scenes on `/activity` or `/approvals`; invent TRAINED/confidence/prices; replace Activity inspector layout.

## Shipped this tranche

1. Thin `creative-grammar` re-export (`EvidenceChip`, `GRAMMAR_BRAND`, `grammarToneForStepStatus`)  
2. **Run execution timeline** — amber spine/`DataStream` while `awaiting_approval`; EvidenceChip for connector result Success/Failed; `data-path-waiting` when a step awaits  
3. **Approvals queue** — pending cards expose `data-path-waiting` + EvidenceChip when `runId` present (“Same path continues”)  

## Explicit non-goals

- Pilot 3 KF productization  
- Autonomous marketing loop timing in product  
- New customer badges beyond existing status labels  

## Checklist

1. ✅ Design (this doc)  
2. ✅ Grammar package  
3. ✅ Timeline + Approvals tone slice  
4. ✅ Unit test for tone map  
