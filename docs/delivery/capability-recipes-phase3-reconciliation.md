# Phase 3 — Capability recipes / dependency graph reconciliation (2026-08-13)

**Status:** CODE shipped + Phase 3.1 Meson/dependency hints @ `da88fa08`; **LIVE PENDING** until push + Supabase egress restored.

## Phase 0 finding (Recipes / Dependency Graph overlap)

| Existing surface | References | Capability-aware? |
|------------------|------------|-------------------|
| `DemoWorkflowSpec` per vendor (`standard_demo_workflows`) | Vendor-specific actions (`hubspot.contacts.create`, `slack.post_message`) | **No** — one vendor per catalog entry |
| `demo_workflow_templates.py` (agent knowledge) | Hard-coded vendor actions + connector ids | **No** |
| `GoalService.generate_workflow` / Meson | Connector names + `CONNECTOR_ACTIONS` flatten | **No** — vendor names in planning prompt |
| `DependencyImpactService` | Connector/agent/workflow entity graph | **N/A** — operational dependency traversal, not business recipes |

**Verdict:** Meson/workflow templates do **not** already cover capability-referenced, cross-stack department recipes. Phase 3 extends the **capability ontology layer** rather than adding a parallel recipe engine.

## What shipped (Phase 3)

| Component | Path | Role |
|-----------|------|------|
| Recipe registry | `backend/app/capability_ontology/recipes.py` | 3 department recipes in capability terms |
| Recipe resolver | `backend/app/capability_ontology/recipe_resolver.py` | Runtime resolution via existing `resolve_capability` |
| API | `GET /api/connectors/catalog/capability-recipes`, `POST .../{id}/resolve` | List + org-connected resolve |
| Tests | `backend/tests/capability_ontology/test_capability_recipes.py` | HubSpot+Slack vs Microsoft+HubSpot stacks, multi-CRM ambiguity |

### Recipes (capability-defined)

1. **`sales.new-lead-enrichment`** — CRM search → document search → agent review → CRM create → channel notify  
2. **`hr.employee-onboarding`** — document search → welcome email → calendar event → channel notify  
3. **`sales.inbound-triage`** — CRM search → channel notify  

Same recipe id resolves differently when connected stack is HubSpot+Slack+Drive vs HubSpot+Teams+Notion vs Gmail+Calendar (onboarding).

## Not in this pass (explicit backlog)

- ~~Meson `generate_workflow` prompt rewrite to prefer capability recipes (Phase 3.1)~~ **DONE** — `meson_recipe_hints.py` + `goal_service._analyze_goal` prompt section @ `da88fa08`
- ~~DependencyImpactService edges for capability recipe steps~~ **DONE** — `capabilityRecipesAffected` on connector removal @ `da88fa08`
- Phase 4 conversational grace — **CODE DONE** @ `da88fa08`; live via `verify-capability-conversational-grace-live.py` (**LIVE PENDING** deploy + Supabase)
- Phase 4 chat multi-turn grace — **CODE DONE**; `verify-capability-conversational-grace-chat-live.py` (**LIVE PENDING**)
- CognitivePlanner recipe wiring — **CODE DONE**; `cognitive_recipe_planner.py` enriches PLAN stage (**LIVE PENDING** kernel trace)
- Phase 2 connector live invoke — `verify-phase2-connectors-live.py` (**LIVE PENDING** deploy + Supabase)

## Verification

```bash
cd backend && python -m pytest tests/capability_ontology/ tests/test_capability_ops_smokes.py tests/test_phase2_connector_smoke.py -q
node scripts/cognitive-regression-suite.mjs   # One Brain non-regression
```

Live (after deploy + Supabase restored):

```bash
python scripts/verify-phase2-connectors-live.py
python scripts/verify-capability-recipes-live.py
python scripts/verify-capability-conversational-grace-live.py
python scripts/verify-capability-conversational-grace-chat-live.py
python scripts/verify-pre-action-card-live.py
```
