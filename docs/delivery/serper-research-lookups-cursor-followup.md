# Cursor follow-up (low priority) — Serper vs Tavily Research Lookups

**Priority:** Low · **Pricing model:** unchanged (keep metered hybrid)  
**Linear:** [STA-341](https://linear.app/staqbot/issue/STA-341/low-evaluate-serper-for-research-lookups-cogs-quality-gate-pricing) (Low)  

**Parent diagnosis:** `docs/delivery/research-lookups-cogs-pricing-diagnosis.md`

## Ask (bounded)

Evaluate Serper as a lower-cost alternative or supplement to Tavily on the research-lookup path.

1. Confirm **real, current** Serper pricing (account or official page — not blog-only).
2. Side-by-side quality on a representative sample of **real** Gravitre lookups (from `usage_records` / research cascade smokes), not invented queries.
3. If quality holds → propose integration (replace vs fallback) + `metadata.provider=serper`; **do not** change allotments/overage/hide decision.
4. If quality fails → close with evidence; keep Tavily.

Published ballpark (verify): Serper ~$0.0003–$0.001/query vs Tavily ~$0.008 → margin only if quality holds.

## Already resolved (do not re-litigate; re-verify only)

| Item | Status | Evidence |
| -- | -- | -- |
| `billing_plans` research keys missing | **Fixed live 2026-08-11** | node/control/command/enterprise 10/60/200/200 + `research_lookup=0.35`; `billing-plans-research-lookups-restore-2026-08-11.json`; commit `b5632611` |
| Gemini grounding “dead code?” | **Not dead; unused winner** | Code primary=google; Railway had GEMINI+Tavily keys, no `WEB_RESEARCH_PROVIDER` → default google → 100% Tavily fallback (35/35). Consolidation: set `WEB_RESEARCH_PROVIDER=tavily` until `google_grounding` appears in usage_records |

## Out of scope

Changing Research Lookups pricing model, allotments, or $0.35 overage.

## Shipped (2026-08-11)

Phase 0 widen sample **GO** (18/18). Serper primary + Tavily fallback integrated; customer allotments/overage unchanged. See `sta341-serper-primary-ship.md`.
