# G8 resolution (2026-09-16)

**Status:** code fix SHIPPED locally — live G8 click-through **not PASS until Railway has the projection `items` mapping**.

## Root cause

`MemoryPromotionService.list_candidates` returns `{ "items": [...] }`.  
`IntelligenceProjectionService` read `promo.get("candidates")`, so canonical `learnings` stayed empty even when `auto_promoted` rows existed. G8 map nodes and Learning cards never hydrated. That is why live batteries labeled G8 **NOT RUN**.

## Fixes

1. `learning_rows_from_promotion_payload` accepts `items` (and legacy `candidates`).
2. G8 API battery scores learns-lens context; records knows fetch errors; optional `g8-promoted-org-learning-map` if isolated/trust orgs still have no insights.
3. UI battery no longer JWT-injects against gravitre.app (`getUser` → `session_expired`). Uses `e2e/.fixtures/billing-users.json` password login.
4. E2E G8 test missing `})` repaired.

## Live evidence still required after deploy

Re-run:

```
EXPECT_SHA=<deployed> python scripts/verify-g8-intelligence-hub-live.py
python scripts/verify-g8-intelligence-hub-ui-live.py
```

Do not upgrade this file to PASS without conversation id / page-context `generatedAt` on the new SHA.
