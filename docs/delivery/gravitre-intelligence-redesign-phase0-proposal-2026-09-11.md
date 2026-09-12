# Gravitre Intelligence Redesign — Phase 0 Inventory & Architecture Proposal

**Status:** DRAFT — awaiting review/approval. No production code changed to produce this document. Per the redesign brief's own Phase 0 mandate: "Do not mutate production before this is reviewed and approved."

**Date:** 2026-09-11
**Author:** Agent-assisted inventory (3 parallel `explore` passes + synthesis)
**Scope:** `/intelligence`, `/intelligence/learning`, `/intelligence/reports`, `/intelligence/predictive`, `/training`, `/models`, `/models/built-in`

---

## 0. Gate check — in-flight work (mandatory pre-condition)

The brief requires: *"Confirm every other in-flight body of work in this program is complete before starting. If anything material is still open, stop and report before proceeding."*

**Finding: material work is open.** Reported to the user before this document was written; user explicitly chose to proceed with Phase 0 (read-only) while flagging the risk in this document, rather than pause.

- **Cognitive Loop Controller** (`docs/delivery/cognitive-loop-controller-live.json`, git `1a5521fc`): PASS on the six-stage loop itself, but carries a `standing_open_item`: `six_stage_loop_vs_spoken_first_audio`, status **UNRESOLVED**, Linear STA-343, `voice_slo_p50: false`. Explicit note: *"Do not treat as a footnote."*
- **Response Composer**: two PARTIALs were closed same-day (`docs/delivery/response-composer-failure-modes-live.json`, git `efa7a398`, 17:21 UTC), but `git log` shows further commits *after* that PASS still touching the loop-stage/Composer interaction (`98dd068f`, `2b10da01` — "Emit honest loop-stage drafts immediately instead of waiting on a Composer LLM hop").
- Concurrent, same-day, direct-to-`main` commits were observed touching `cognitive_loop_controller.py`, `response_composer.py`, `assistant_sse.py`, `tool_registry.py`, `voice_session_service.py`, `agent_intelligence.py` from a session other than this one.

**Implication carried through this whole document:** every place below that says "Cognitive Loop Controller" or "Response Composer" is a stable foundation should be read with this caveat — the stage-timing/narration behavior these two systems produce is still moving. Phase 2 (motion-system mapping) is the most exposed to this risk (see §9).

---

## 1. Executive summary — go/no-go per subsystem

| Subsystem | The brief assumes | What's actually true today |
|---|---|---|
| Cognitive Loop Controller | "already completed and live... reused directly, not rebuilt" | Real 6-stage loop (`PERCEIVE→RETRIEVE→PLAN→ACT→OBSERVE→LEARN`) with real audit + real per-stage evidence — **but the structured stage payload is emitted over SSE and never consumed by the web frontend today** (frontend only reads the human-readable `progressSteps` strings). STA-343 open. |
| Response Composer | "the real, mandatory output layer... every answer... routes through it" | Real and prod-verified on the **main chat/voice path** (`agent_intelligence.py` → `assistant.py`). **Not proven universal** — workflow builder, Meson canvas, and job notifications appear to bypass it via older `gravitre_voice`/`finalize_user_facing_message` helpers. |
| Motion System (Pulse/Flow/Trace/Resolve) | "reused directly, not rebuilt" | These four exports are **Framer Motion scroll-reveal entrance animations for marketing pages** (opacity/x/scale/blur transitions on `whileInView`). They have **zero backend wiring** today. Reusing them "directly" for real-time backend-state visualization is not literally possible — they'd need new state-driven variants built on the *same visual language*, which is a fair reading of "reused" but not "as-is." |
| AI State ↔ Backend State Matrix | "reused directly, not rebuilt" | The **full cross-surface matrix exists only as a doc table** (`docs/delivery/ui-2-0-phases-2-6-proposals-2026-09-04.md` §Phase 4). The only **code** artifact with this name (`apps/web/lib/ai-state-matrix.ts`) is narrowly scoped to sanitizing chat/voice activity-label strings — it is not a general AI-state-to-visual-state matrix. |
| PredictiveOperationsEngine | implied stable, already fixed | Real, live, and (per the same-program predictive-ops 500 fix shipped today, commit `824a6ac0`) verified working across all 6 domain packs in production. Per-model and per-domain status is queryable. **No unified "five pillar" (KNOWS/LEARNS/PREDICTS/ACTS/IMPROVES) aggregation exists.** |
| GIBE | implied a real backend module | GIBE is a **brand name for a cluster of existing intelligence surfaces** (outcome events, trust/confidence, runtime-honesty labeling, training readiness), not one backend service with one API. Real, but a composition layer, not a data product. |
| Knowledge Fabric | "already-real data" for Phase 6 | **Two genuinely different things share loose naming**: (a) platform-shared curated packs (legal/finance/HR/etc — `knowledge_sources`/`knowledge_documents`/`knowledge_chunks`) — stable, PASS'd, ready to build on; (b) org-specific knowledge graph / "One Brain" (`org_knowledge_nodes`/`org_entity_relationships`) — real but explicitly documented elsewhere as **partially composed**, not one finished product. Phase 6 of the brief ("What Gravitre Knows") needs to pick one or explicitly show both, distinctly labeled. |
| Model Studio infra | "built on real, existing training/model infrastructure" | Registry (`registry.py`), training (`training.py`/`trainingApi`), and catalog-train (`ml_admin.py`) primitives are all real. **No existing intent-first orchestration** — today's flow is 4-5 separate API calls a human has to sequence manually; an intent-first wizard is genuinely new frontend+light-backend work, not a reskin. |
| Nodus design system | implied the settled visual owner | Confirmed as the **live, currently-authorized production direction** (Gate 0 approved 2026-09-06, P1–P15 shipped 2026-09-07) — but **no phase has yet claimed authenticated visual-fidelity PASS**. Building on Nodus tokens is correct; claiming the redesign inherits a "done" visual system would be inaccurate. |
| Agents 4.0 fleet graph | not mentioned in brief, but directly relevant to Phase 10 | **Directly reusable head start.** `/agents` already has a real, live, data-driven 2D SVG relationship graph (real `parent_of`/`delegates_to`/`uses_connector` edges, no invented edges) shipped as of 2026-09-10. Production human sign-off is still blank in the Phase 6 acceptance doc — should close that loop before treating it as a finished dependency. |
| Three.js/WebGL | Phase 2 says "used only for the Core itself, lazy-loaded" | **Not currently a dependency.** One orphaned WebGL component exists (`intelligence-network-webgl.tsx`, built for UI 2.0, never mounted to any page) plus one small raw-WebGL mesh-gradient background on the auth page. Adding Three.js would be a **net-new dependency**, not an extension of existing usage. |

**Overall verdict:** the individual capabilities are almost all real. The specific *claim* in the brief that they already "feed a shared, real data layer this new Overview can draw from directly" is **not accurate as stated** — every cross-cutting surface the redesign wants (Overview pillars, structured loop-stage UI, unified approval "amber pulse", intent-first Model Studio) requires a **new, thin aggregation/orchestration layer** over real existing primitives. This is good news (no new ML/data engineering needed) but it does mean Phase 0's assumption of "just wire up the Overview" understates the work by roughly one integration layer.

---

## 2. Route inventory (current state, all 7 pages)

| Route | File | AppShell/useAuth | Notes |
|---|---|---|---|
| `/intelligence` | `apps/web/app/intelligence/page.tsx` | Yes | Hub: `GibeHonestyStrip`, `TrainingReadinessStrip`, `HeuristicSuggestionCards`, `IntelligenceHealthGrid`, `SimulationCard`, link groups to all 6 other pages + `/metrics`, `/intelligence/memory` |
| `/intelligence/learning` | re-export of `apps/web/app/admin/intelligence/page.tsx` | Yes | 9 tabs: Overview, Memory, Relationships, Quality, Outcomes, Trends, Engine, Performance, Recent turns |
| `/intelligence/reports` | `apps/web/app/intelligence/reports/page.tsx` | Yes | 11 tabs, all department-scoped `PackKpiPanel` instances + ROI + Executive scorecard |
| `/intelligence/predictive` | `apps/web/app/intelligence/predictive/page.tsx` | **No** (page-level; still edge-gated via `proxy.ts`) | 6 domain packs, all fixed as of `824a6ac0` |
| `/training` | `apps/web/app/training/page.tsx` (~1360 lines) | Yes | Datasets / Jobs / Fine-tunes tabs |
| `/models` | `apps/web/app/models/page.tsx` | Yes | Custom/registered model registry (`mlModelsApi`) |
| `/models/built-in` | re-export of `apps/web/app/intelligence/models/page.tsx` | Yes | GRAVITRE_ML_CATALOG showcase (26 models: 14 TRAINED, 11 PLANNED, 1 DISABLED) |

**Duplication/consistency findings:**
- `/intelligence/learning` and `/models/built-in` are **already aliases** of other real routes (`admin/intelligence`, `intelligence/models`) — this precedent means Phase 1's "preserve every existing route as an alias" is a **proven, already-used pattern** in this codebase, not a new technique.
- `/intelligence/predictive` is the one page-level inconsistency (no `AppShell` wrapper) — should be fixed as part of migration regardless of the redesign, for visual-chrome consistency alone.
- "Built-in Models folds into Models unless a real, strong technical reason prevents it": **no strong technical reason found.** `/models` (registry) and `/models/built-in` (catalog) already read from mostly-disjoint but architecturally-compatible APIs (`mlModelsApi` vs `intelligenceApi.modelCatalog()`); folding to a single `Models` destination with a `Registry`/`Catalog` (or `Custom`/`Built-in`) toggle is straightforward and recommended.

---

## 3. Component reuse strategy

**Reuse as-is (no changes needed):**
- `AppShell`, `GravitrePageHeader`, `GravitreMetric`, `EmptyState`/`ErrorState`, `nodus-product/*` primitives — the whole Nodus product component layer.
- `intelligenceApi.*`, `trainingApi.*`, `mlModelsApi.*` — all existing SWR-backed data hooks; the redesign's new pages should call these same functions, not new ones, for anything that isn't a genuinely new aggregation.
- `PackKpiPanel`, `AgentRoiPanel`, `ExecutiveIntelligenceScorecard` (Reports), `RelationshipsWorkspace` (knowledge graph), `BuiltInModelsBrain` (catalog cards) — all real, working, and should be linked-to/embedded-in the new IA, not rewritten.
- `HeuristicSuggestionCards`, `RecommendationExplanation` — closest existing thing to Phase 3's "What matters now" layer; extend rather than replace.
- Agents 4.0 `GraphView`/`TeamView`/`GravitreAgentNode`/`nodus-fleet-chrome` (`apps/web/components/agents/fleet-v4/*`) — directly reusable pattern for Phase 10's "agents as personas around the shared core."

**Reuse the visual language, but cannot reuse the implementation as-is:**
- `GravitrePulse`/`Flow`/`Trace`/`Resolve` (`apps/web/components/marketing/system/motion.tsx`) — these are literally `whileInView` scroll-reveal aliases with no state input. A real Intelligence Core needs new components that accept a live state prop and reuse these four transitions' *visual signature* (the specific opacity/scale/blur curves), not the components themselves.
- `GravitreIntelligenceCore`/`GravitreDepartmentNetwork`/`GravitreSignalPath` (`apps/web/components/marketing/system/department-network/*`) — excellent visual precedent (hub + department nodes + animated signal paths, all CSS+SVG+Framer Motion, no WebGL) but currently driven by a **scripted marketing story** (`useNetworkStory`/`NETWORK_SCENARIOS`), not live data. The path of least risk is to **fork this visual pattern** into a new `apps/web/components/intelligence/intelligence-core.tsx` driven by real props, rather than trying to make the marketing component "dual-purpose."

**Net-new (nothing to reuse):**
- Structured cognitive-loop-stage UI (backend emits it; nothing on the frontend consumes `routing.stages`/`loopId` today — this is 100% new frontend work, though zero new backend work).
- Unified Overview aggregation (KNOWS/LEARNS/PREDICTS/ACTS/IMPROVES) — no existing endpoint.
- Unified "pending approval" index — chat HITL state lives in `conversation.task_state`, workflow approvals live in `/api/approvals`, memory-promotion pending lives in `memory_promotion_candidates` — three different stores need one read-side aggregation.
- Model Studio's intent-first Create-Model wizard.

---

## 4. Intelligence Core — proposed data model

Given §1's findings, the Core cannot be "purely a visualization of existing data" — it needs one new, real (not simulated) aggregation endpoint. Proposed shape (backend-authoritative, computed from tables that already exist — no new ML, no new tables beyond a thin view/query):

```
GET /api/intelligence/core/state?org_id=...

{
  "core": {
    "processing": bool,              // any active cognitive-loop turn for this org right now (from live SSE/session state, not audit)
    "last_learn_at": "2026-09-11T...Z" | null,   // MAX(created_at) from intelligence_outcome_events
  },
  "departments": [
    {
      "id": "sales",
      "connected_sources": 3,        // count of connected connectors tagged to this department
      "active_agents": 2,           // count from agents table filtered by department
      "signal_count_24h": 41,       // count of agent_action_outcomes / query_patterns rows, last 24h
      "pending_approvals": 1,       // from the 3-store aggregation in §7
      "last_prediction_confidence": 0.42 | null,  // most recent domain-pack risk_score for this department's mapped domain, or null if insufficient_data
    },
    ...
  ],
  "edges": [
    // Reuses the exact honesty discipline from agents-fleet-graph.ts:
    // only real edges (parent_of, delegates_to, uses_connector, knowledge-fabric relationship rows),
    // never invented "collaborates"/"escalates" edges.
  ]
}
```

This single endpoint is the **one genuinely new backend surface** this whole redesign needs at its foundation. Everything else (Learning/Predictions/Performance/Models pages) can be built by linking to/embedding the existing endpoints inventoried in §1 and §2.

---

## 5. Motion-system mapping (per brief's required table, honesty-checked)

| Brief's semantic | Real backend condition available today? | Source |
|---|---|---|
| PULSE — processing | Yes — SSE turn-in-progress state, or poll `conversations` with an open turn | existing SSE infra |
| FLOW INWARD — ingestion | Partial — connector sync events exist in audit (`connector.*` actions); needs a live-tail, not built today | `audit_events` |
| RELATIONSHIP FORMATION — new graph edge | Yes — `org_entity_relationships` insert events | `admin_intelligence.py` relationships endpoints |
| FLOW OUTWARD — new prediction/signal | Yes — `predictive-ops/domain/{domain}` poll (already 60s-interval in current predictive page) or `intelligence_outcome_events` insert | existing |
| TRACE — live agent action | Yes — existing plan-bar/checklist SSE (`progressSteps`), reused **as-is** per §3 | `ai-workspace.tsx` SSE consumption |
| RESOLVE — confirmed successful outcome | Yes — F6 follow-up verification is real (362/362 catalog coverage per `cognitive-loop-controller-live.json`) | `agent_action_outcomes` / F6 verification |
| AMBER PULSE — pending approval | Yes, but needs the 3-store aggregation from §7 | `conversation.task_state` + `/api/approvals` + `memory_promotion_candidates` |
| DASHED/FADED EDGE — low confidence | Yes — existing `confidence_is_estimate`/`confidence_source` fields already used elsewhere (Module C honesty pattern) | `sufficiency` evidence, model `runtime_status` |

**Risk flag (carried from §0):** TRACE and PULSE both key off cognitive-loop-stage timing, which is the exact mechanism under active same-day iteration (STA-343). Building the Core's animation timing against today's stage-latency behavior risks needing rework once STA-343 lands. Recommendation: build the Core against the **audit/event data**, not against live per-token SSE timing, so a fix to voice dead-air doesn't force a Core rewrite — only a possible retuning of animation duration constants.

---

## 6. Ask/Why interaction models

- **Ask Gravitre** (Phase 4): route through the existing `assistant.py` → `AgentIntelligence` → Response Composer path used by chat today — this is the one path confirmed prod-verified for Composer (§1). Do **not** build a second chat implementation; render the existing SSE response inside a new composed-UI shell that maps `pending_task`/tool outputs to KPI-card-like components (new frontend components; existing data).
- **Why? evidence graph** (Phase 5): the `sufficiency` evidence block already recorded in the RETRIEVE stage (`assessor`, `reason`, `gaps`, `confidence_source`, `assessment_confidence`) is a real, ready-made source for this — but it's currently only visible in probe/audit JSON, not surfaced to any UI. This is a new frontend surface over already-real data (no backend work beyond exposing an existing per-turn field via API, which may already be queryable via `cognitive_turns.py`).

---

## 7. Status-vocabulary mapping — implementation notes

The brief's translation table (Untrained→"Needs training", etc.) maps cleanly onto the **existing** `runtime_status` values already computed in `get_org_model_status()` (`model_catalog.py`): `heuristic`/`data_gate`/`trained`/`not_trained`/`planned`/`disabled`. This is a **pure display-layer lookup table** — zero backend change required, exactly as the brief specifies ("display-layer translation of real, existing states only").

The six-question card structure (What/Why/Learns-from/How-well/Where/Improve) is answerable today from:
1. What / Why → `GRAVITRE_ML_CATALOG[model]["use_cases"]` (real)
2. Learns from → `activation_requirement` / `data_counts` from `_count_org_data_points()` (real)
3. How well → `outcomeScores` from strategy performance ledger (real, sparse — many will honestly say "not enough usage yet")
4. Where used → **not currently tracked at model granularity** — this is a real gap; needs either a new join (which agents/workflows reference this model_name) or an honest "not tracked yet" fallback
5. Improve → maps to the "Improve this model" actions in Phase 8.5 — mostly UI-only given existing training APIs

---

## 8. Model Studio flow — feasibility

Confirmed backend primitives exist for a wizard *composing* existing calls (§1.6). Concretely:

- Step 1 (What to predict) → maps to `GRAVITRE_ML_CATALOG` types + `mlModelsApi.create` type enum (`classifier|fine_tuned_llm|anomaly_detector|forecaster`) — **note: registry only supports 4 types today**, fewer than the brief's Step 1 options (Predict outcome / Classify / Score-rank / Detect anomalies / Forecast / Improve agent / Template / Advanced). Mapping every brief option onto one of the 4 registry types is possible but should be made explicit and honest in the wizard copy (e.g. "Score or rank records" → `classifier` under the hood).
- Step 2 (data source) → real connector list already available (`connectorsApi.list()`), already used on `/models`.
- Step 3 (what to predict, plain language) → new, thin intent-capture step; can pre-fill Step-4-and-beyond's advanced fields via existing catalog metadata, but there is **no existing intent→config inference backend** — this mapping would initially need to be a simple static lookup table (safe, no new ML), not an LLM-driven inference (which would be new, riskier scope not requested).
- "Improve this model" actions → all map to existing `trainingApi` methods (add examples, new data source, retrain) except "Correct bad predictions" / "Adjust what the model considers important", which have no existing backend hook found — flagged as a real gap needing either scope-reduction (drop for v1) or new backend work (feedback-loop endpoint).

**Honest verdict:** Model Studio is buildable as a new frontend wizard over existing endpoints for ~80% of the specified flow. The other ~20% (intent inference beyond a static lookup, "correct bad predictions" feedback loop, "where is this model used" tracking) needs either explicit scope-reduction for v1 or small, named new backend work — should not be silently invented as if already present.

---

## 9. Migration plan (routes) and regression risk

Given the two existing precedents (`/intelligence/learning` and `/models/built-in` are already re-export aliases), the exact same pattern extends cleanly:

| Old route | New primary route | Migration mechanism |
|---|---|---|
| `/intelligence` | `/intelligence` (Overview) | Same file, new content — lowest risk |
| `/intelligence/learning` | `/intelligence/learning` | Unchanged path, evolve `admin/intelligence` content |
| `/intelligence/predictive` | `/intelligence/predictions` | New route renders real content; old path becomes a re-export alias (proven pattern) |
| `/intelligence/reports` | `/intelligence/reports` | Unchanged — first-class per Phase 9 |
| `/training` | folds into `/intelligence/models` → `Model Studio` tab, OR stays as deep-link target from "Improve this model" | Needs explicit decision — see open question in §10 |
| `/models` | `/intelligence/models` (Models destination) | Old path becomes re-export alias |
| `/models/built-in` | `/intelligence/models` (Catalog view/tab) | Already an alias today — no new risk |

**Top regression risks, ranked:**
1. **STA-343 / Composer-loop churn (§0)** — building Phase 2 animation timing against a moving target.
2. **`/intelligence/predictive` missing `AppShell`** — must be fixed in the same PR that renames/aliases it, or the alias will carry the inconsistency forward.
3. **Admin-only gating on 40/40 `admin_intelligence.py` endpoints** — the redesign's Overview must either accept it will only work fully for admins, or explicit new non-admin-scoped endpoints are needed for the "novice business user" persona the brief targets. This is a **real, unresolved product question**, not just an engineering detail — see §10.
4. **Loss of `?agentId=`/`?section=` query-param behaviors** currently used to deep-link into `/training` and `/intelligence` — must be preserved across the IA change.
5. **Agents 4.0 production sign-off still blank** (per its own Phase 6 doc) — if Phase 10 extends `GraphView`, it's extending a component whose own acceptance isn't fully closed yet.

---

## 10. Open questions requiring your decision before Phase 1 starts

1. **Admin-only gating.** Every one of the 40 `admin_intelligence.py` endpoints requires `require_admin`. The brief's "novice business user... understand in 30 seconds" persona implies non-admin users should see the Overview too. Do you want: (a) Overview restricted to admins only for v1, (b) new non-admin-scoped read endpoints added (real backend work, currently out of the brief's explicit scope), or (c) something else?
2. **`/training` destination.** The brief's nav list doesn't include `/training` as a top-level item, but Phase 8.5's "Improve Existing Model" actions map directly onto `/training`'s existing datasets/jobs/instructions UI. Should `/training` become a tab inside Model Studio, stay as its own deep-linkable destination reachable only from "Improve this model," or something else?
3. **STA-343 timing.** Given §0/§9-risk-1, do you want Phase 2 (motion mapping) sequenced to start only after STA-343 closes, or proceed now against audit-event data (safer, per §5's recommendation) and accept re-tuning risk later?
4. **Knowledge Fabric vs org graph naming (Phase 6).** Should "What Gravitre Knows" show the platform Knowledge Fabric packs, the org-specific knowledge graph, or both — clearly and separately labeled, given they are genuinely different systems at different maturity levels?
5. **WebGL/Three.js.** Confirmed as a net-new dependency (§1). Approve adding it, or prefer the CSS+SVG+Framer-Motion approach already proven in the marketing department-network component and the Agents 4.0 graph (no WebGL, already shipped, already accessible)?

---

## 11. Proposed phase sequencing (revised from the brief given the above)

Unchanged from the brief's own Phase 1–14 structure, with two insertions:

- **Phase 0.5 (new):** Build the one real new aggregation endpoint from §4 (`/api/intelligence/core/state`) and the 3-store approval-pending aggregation from §5/§7. This is the actual prerequisite the brief's Phase 0 assumed already existed. Everything downstream depends on this being real before any UI work claims to be "data-driven, not decorative."
- **Phase 2 (as brief), sequencing note:** proceed against audit/event data (not live per-token SSE timing) per §5, to decouple from STA-343.
- All other phases as specified in the brief, pending your answers to §10.

---

## 12. Decisions (resolved 2026-09-11, governing all Phase 1+ work)

The five open questions in §10 are resolved as follows. This section is an
append — §10 is left intact above as the original creation-time record.

1. **Admin-only gating → (b), scoped precisely, done in Phase 1.** Overview
   must be reachable by real, non-admin org members, not admin-only. Shipped:
   `GET /api/admin/intelligence/outcomes`, `/simulations`, `/trust-summary`,
   and `/business-impact` (the fourth needed for the new Performance
   destination, same category of org-scoped read analytics) switched from
   `require_admin` to `require_org_member` in `backend/app/routers/admin_intelligence.py`.
   `golden-signals` was evaluated and intentionally left admin-only — it has
   no `org_id` parameter at all and is platform-wide deploy/ops health, not
   org business data, so it is out of scope for this fix. All other 36
   admin-mutation endpoints on that router are untouched. Regression-tested
   in `backend/tests/test_admin_intelligence_overview_permissions.py`
   (7 tests: 3 fixed reads reachable by a member, business-impact reachable,
   golden-signals still gated, a real admin-mutation route still gated, admin
   access to the fixed routes unaffected).
2. **`/training` destination → stays its own top-level primary-nav
   destination**, alongside Model Studio, not folded into it. Nav order:
   Overview, Learning, Predictions, Performance, Models, Model Studio,
   Training, Reports.
3. **STA-343 timing → proceed now.** Phase 2 motion-mapping work is not
   blocked on STA-343 closing; it is sequenced as real, state-driven
   components wired to genuine backend events (not the scroll-reveal
   marketing primitives), independent of the voice-loop defect.
4. **Knowledge Fabric vs org graph (Phase 6) → show both, separately,
   honestly labeled.** Never merged into one graph — they are genuinely
   different systems (platform-shared curated packs vs. tenant-specific
   entity graph) at different maturity levels.
5. **WebGL/Three.js → rejected.** The Intelligence Core will be built with
   the same CSS+SVG+Framer-Motion approach already proven in the marketing
   department-network component and the Agents 4.0 `GraphView` (shipped
   2026-09-10) — no new WebGL dependency.

## 13. Phase 1 — what shipped (2026-09-11)

- **New primary Intelligence sub-navigation** (`components/intelligence/intelligence-hub-tabs.tsx`,
  the same `HubTabs` primitive as `AgentsHubTabs`): Overview, Learning,
  Predictions, Performance, Models, Model Studio, Training, Reports — all
  first-class, no "Advanced" drawer. Mounted on `/intelligence`,
  `/intelligence/learning` (`/admin/intelligence`), `/intelligence/predictive`,
  `/intelligence/reports`, `/models`, `/intelligence/models`, and `/training`.
- **Zero URL renames.** `/intelligence/predictive` keeps its URL; the nav
  simply labels that tab "Predictions." No bookmark or deep link breaks.
- **Real bug fix alongside the redesign:** `/intelligence/predictive` had no
  `AppShell` at all (flagged as risk #2 in §9) — fixed, page now has the
  standard shell, top bar, and the new sub-nav.
- **Two new, real, first-class destinations:**
  - `/intelligence/performance` — composes the existing, real
    `BusinessImpactCard` and `AgentRoiPanel` components (org business-impact
    score, revenue-risk items, hours automated, estimated value) plus the
    same outcome/confidence metrics pattern already on Overview. No new data
    model invented; honest "—" and empty states preserved from the source
    components. A dedicated Phase 7 KNOWS/LEARNS/PREDICTS/ACTS/IMPROVES
    framing pass is still separate, later work.
  - `/intelligence/model-studio` — a real landing page whose four actions
    (Create Model, Improve this model, Retrain, Add Knowledge/Data) link
    directly into existing, working screens (`/models?action=register`,
    `/models`, `/training`). The full guided intent-first wizard specified
    in Phase 8.5 is explicitly **not** built yet and is disclosed as such,
    in-product, on the page itself — not silently dropped.
- **Built-in Models folded into Models**, per the approved "no strong
  technical reason to keep them separate" finding: `/models` now has a real
  "Registry" / "Built-in models" tab pair. The built-in panel is the exact
  same component (`BuiltInModelsPanel`, extracted from
  `app/intelligence/models/page.tsx`) reused, not duplicated — and
  `/intelligence/models` / `/models/built-in` still resolve, unchanged, for
  existing bookmarks.
- **Verification:** `tsc --noEmit` clean across the whole `apps/web`
  workspace; `eslint` on every touched/new file — 0 errors (pre-existing,
  unrelated warnings only); backend `pytest` green for the new permissions
  test file plus the pre-existing `admin_intelligence.py`-adjacent test files
  (`test_admin_intelligence_evaluations.py`, `test_knowledge_graph_traverse_admin.py`).
- **Explicitly not done in this slice** (tracked, not silently dropped):
  Phase 2 motion-mapping components, Phase 3 Overview 3-layer restructure,
  Phase 4 Ask Gravitre composed UI, Phase 5 Why? evidence graphs, Phase 6
  knowledge/graph visualization, Phase 7 full business-language reframe,
  Phase 8 Business/Technical toggle, Phase 8.5 guided Create Model wizard,
  Phases 9–14. Live human-verification and prod deploy/redeploy evidence for
  this Phase 1 slice have not yet been captured as of this write-up.

## 14. Phase 1 verification — resolved (2026-09-11)

- **Background route-check, confirmed:** all 8 Intelligence sub-nav
  destinations exist and render real content in production (verified via a
  `browser-use` subagent pass plus a direct CDP check from an authenticated
  admin session). `/intelligence/performance` rendered a genuine Business
  Impact Score and an honest empty/dash ROI table; all 8 tabs were clickable.
  A round of raw `fetch()` calls against `outcomes` / `simulations` /
  `trust-summary` / `business-impact` returned 401 in both the subagent's
  check and my own direct check — but a controlled comparison against
  `engine-settings` (a route this fix never touched, still genuinely
  admin-gated) returned the *same* 401, proving the 401s were a raw-fetch
  test artifact (missing the app's real `Authorization`/`x-org-id` headers
  from `apps/web/lib/fetcher.ts`), not a real permission regression. Genuine
  non-admin, hands-on click-through verification was handed off to be done
  directly by the requester rather than attempted further by the agent.
- **`.vercel` project-name mismatch, investigated and resolved as harmless:**
  `apps/web/.vercel/project.json` links to a Vercel project literally named
  `gravitre-saas-backend`. Confirmed via `vercel project ls` that this exact
  project's Latest Production URL is `https://gravitre.app` (the real
  production frontend, confirmed serving `Server: Vercel` /
  `X-Powered-By: Next.js`), consistent with the timing of the Phase 1 push.
  The name is a confusing historical artifact, not a live misconfiguration —
  the link is correct and the file is gitignored/untracked, so it has no
  bearing on the real CI/CD path either way. Separately noted, not touched:
  a second, apparently-stale Vercel project named `web`
  (`web-drab-five-19.vercel.app`, last updated 7 days prior) that does not
  serve any real traffic. No fix applied to either project, per explicit
  instruction that deploy-infrastructure changes require a separate go-ahead.

## 15. Phase 2 — what shipped (2026-09-11)

Scope, per decisions #3 and #5: real, state-driven Motion System components
sharing the existing visual signature (CSS + SVG + Framer Motion — no
WebGL/Three.js), wired to genuine backend events, independent of STA-343.

- **New backend endpoint — `GET /api/intelligence/core/state`**
  (`backend/app/routers/intelligence_engine.py`, `require_org_member` — same
  non-admin access model as `/models/catalog` and `/training-readiness` on
  this router, consistent with decision #1's spirit). Aggregates, per org,
  entirely from live tables, never simulated:
  - Department breakdown from `intelligence_outcome_events.department` (the
    same column already backing `OutcomeLearningService.get_department_outcome_summary`)
    over a real recency window (default 24h) — a new public
    `OutcomeLearningService.fetch_recent_events()` wrapper adds hour-level
    cutoff filtering on top of the existing `_fetch_events` primitive.
  - Org-level (not department-attributable — today's schema doesn't support
    that join) real signals: pending workflow approvals (`workflow_runs`),
    pending memory-promotion approvals (`memory_promotion_candidates`), and
    active agent swarm runs (`agent_swarm_runs`).
  - Departments with zero real events in the window simply do not appear in
    the response — the endpoint never invents a department entry the org has
    no signal for. 7 new backend tests (`test_intelligence_core_state.py`,
    `test_outcome_learning_service_recent_events.py`) cover: non-admin
    reachability, real per-department attribution (a `sales`-tagged event
    never leaks into `marketing`), org-level (not fabricated per-department)
    approval/run counts, and honest degrade-to-zero on downstream failures.
  - **Known, disclosed limitation:** this is a polled snapshot (frontend
    refreshes every 20s), not a sub-second live push — the "PULSE" motion is
    real recent activity, not a live SSE feed. No existing org-wide SSE
    activity stream exists to source truer real-time push from today.
- **New frontend component — `GravitreIntelligenceCoreLive`**
  (`apps/web/components/intelligence/core/`): a real, live successor to the
  marketing `GravitreDepartmentNetwork` story, reusing the same card/hub/edge
  visual language (rounded white department cards, Nodus conic-spin hub,
  sweeping-gradient SVG edges) but driven entirely by
  `GET /api/intelligence/core/state` polled every 20s — no scripted beats, no
  fixed department set. Visual states (`idle`, `flow-inward`, `trace`,
  `pending-approval`, `resolved`, `low-confidence`) map 1:1 to the backend
  response. Honest empty state when an org has no real activity in the
  window, rather than an empty diagram or placeholder nodes. Mounted on the
  Intelligence Overview page (`/intelligence`), directly under the new
  sub-nav.
- **Verification:** backend — 7/7 new tests pass, plus the full pre-existing
  `test_intelligence_engine.py` (18 tests) and Phase 1's
  `test_admin_intelligence_overview_permissions.py` (7 tests) all still pass
  (39/40 → 40/40 after one test fixture fix, no regressions). Frontend —
  `tsc --noEmit` clean across the whole `apps/web` workspace; `eslint` on
  every new/changed file — 0 errors (pre-existing, unrelated warnings only).
- **Explicitly not done in this slice:** live prod deploy + prod re-run
  evidence for this Phase 2 slice (not yet committed/pushed/redeployed as of
  this write-up — that is the very next step after this note); the
  packet-capsule transfer animation from the marketing precedent (kept to a
  simpler gradient-sweep edge for this first real slice); wiring the
  remaining Phase 3–14 scope (3-layer Overview restructure, Ask Gravitre,
  Why? evidence graphs, knowledge/graph visualization, business-language
  reframe, etc.) — all still pending, unchanged from §13's list.

## 16. Phase 2.5 — what shipped (2026-09-11)

Scope: ban bare lifecycle status words anywhere in the user-facing product;
translate real, existing technical states into the brief's business-friendly
phrases + honest one-line context; render the real six-question model-card
structure. Display-layer only — no new technical states invented anywhere.

- **New shared module — `apps/web/lib/intelligence/status-language.ts`**:
  the brief's exact 8-row translation table (Untrained/Training/Trained/
  Deployed/Evaluating/Stale/Failed/Fine-tuning), plus honest extensions for
  every other real status value already produced by this codebase today
  (`heuristic`, `data_gate`, `planned`, `disabled`, `draft`, `validating`,
  `archived`, `ok`, `not_available`, `insufficient_data`). An unmapped real
  status is humanized, never given a fabricated friendly phrase, and its
  gap is disclosed in the returned `detail` string.
- **New shared component — `ModelStatusBadge`**
  (`apps/web/components/intelligence/model-status-badge.tsx`): the one place
  a status renders to a user — always a friendly phrase, paired with a
  visible one-line context sentence (default) or a title tooltip for the
  densest table/chip rows where the surrounding card already carries
  context. Replaced every bare `<Badge>{status}</Badge>` call site found in
  the Phase 2.5 inventory: built-in models directory card, detail panel, and
  table row; the built-in model profile page header; predictive-ops domain
  cards; the custom model registry list rows and detail-page header/metric.
- **New shared component — `SixQuestionsPanel`**
  (`apps/web/components/intelligence/six-questions-panel.tsx`): renders the
  brief's six-question structure (What / Why / Learns-from / How-well /
  Where-used / How-to-improve). Mounted as a "Quick answers" section on both
  full model-detail surfaces — the built-in catalog profile page and the
  custom registry's `ModelDetailInsights` — sourced entirely from data
  already fetched on those pages. The one genuine, disclosed gap found in
  the Phase 0 inventory (model usage isn't tracked at the individual
  agent/workflow level) is rendered as an explicit gap answer, never
  fabricated; real use-case tags are shown alongside it where they exist.
- **Not touched, deliberately**: `GibeHonestyStrip` and
  `decision-transparency-card.tsx` already paired their runtime-honesty
  chips with a detail sentence/tooltip via the pre-existing
  `presentModelRuntime()` (Module C) — these already satisfied the
  "context in the same view" rule before this pass and were left as-is to
  avoid regressing Module C's honesty semantics.
- **Verification**: `tsc --noEmit` clean across `apps/web`; `eslint` on
  every touched/new file — 0 errors (2 pre-existing, unrelated warnings
  confirmed via `git diff` to predate this change). 5 new unit tests for
  the translation table (`status-language.test.ts`) plus the pre-existing
  `built-in-model-catalog.test.ts` (3 tests) both green.
  Pushed as `b98b18fd`; confirmed live via the Vercel deployment API
  (`get_deployment`) showing `githubCommitSha: b98b18fdd80d2fe5abdcf7917be0d1a9532d40e0`,
  `readyState: READY`, aliased to `gravitre.app` (production). A live,
  authenticated `browser-use` pass confirmed the exact new phrases
  ("Estimating with rules", "Not built yet", "Turned off", "Needs more
  data", "Not available") rendering on `/models/built-in` and
  `/intelligence/predictive` in production, and confirmed the full 6/6
  "Quick answers" panel with real content on a built-in model detail page
  (`capacity_forecaster`), with zero console errors on every page checked.
  **Honest caveat**: the `/models` registry list badge itself could not be
  visually confirmed in that same pass because the authenticated test org
  has zero registered custom models (empty state) — the badge text the
  subagent reported on that page did not match this change's exact phrases
  and most likely came from a different UI element on the page, not the
  `ModelStatusBadge` component. `tsc`/`eslint`/unit tests cover that call
  site; live visual confirmation on a populated registry is still open and
  not claimed as PASS.

## 17. Brief-Phase 3 — Overview: Three Real Layers (what shipped, 2026-09-11)

Scope: restructure `/intelligence` (Overview) into the brief's three layers —
Layer 1 (Intelligence Core, already live from Phase 2) unchanged; a new
Layer 2 "What matters now"; a new Layer 3 "Ask Gravitre"; plus a business-
friendly KNOWS/LEARNS/PREDICTS/ACTS/IMPROVES summary. Nothing existing on
the page was removed — all new sections were inserted between the Core
visualization and the pre-existing Module C strip.

- **Layer 2 — `WhatMattersNowPanel`**
  (`apps/web/components/intelligence/what-matters-now.tsx`): reads
  `assistantApi.businessSignals()` (already server-ranked by
  `quality_score` in `recommendation_quality_engine.rank_recommendations`),
  re-sorts defensively client-side, caps at 5. Honest empty state
  ("Nothing ranked as urgent right now") when the org has no qualifying
  signals — never a placeholder card. Links out to `/ai?prompt=...` for
  more detail.
- **Layer 3 — `AskGravitreEntry`**
  (`apps/web/components/intelligence/ask-gravitre-entry.tsx`): compact,
  visually subordinate to Layers 1-2 (no large hero treatment). Real
  suggested questions from `assistantApi.dailyBriefing().suggestions`;
  falls back to the brief's own three example questions ("What changed
  today?" / "What needs attention?" / "What have you learned?") only as
  clickable link *labels* when the org has no live briefing yet, with an
  explicit on-screen disclosure that these are examples, not live answers.
  Every chip deep-links to the same `/ai?prompt=` pattern used elsewhere in
  the product (confirmed real query-param handling in `app/ai/page.tsx`).
- **Five-pillar summary — `IntelligencePillars`**
  (`apps/web/components/intelligence/intelligence-pillars.tsx`): KNOWS =
  `entity_count`/`relationship_count` from `intelligenceApi.knowledgeGraph()`;
  LEARNS = ready-to-train count from the existing
  `summarizeTrainingReadiness()` helper (reused, not duplicated) against
  `trainingReadiness()`; PREDICTS = count of `artifact_loaded` models from
  the already-fetched `modelCatalog()`; ACTS = `activeAgentRuns` from
  `intelligenceApi.coreState()` (same endpoint/SWR key as the Phase 2 Core
  visualization — deduplicated, not double-polled) plus
  `recommendation_created` count from outcomes; IMPROVES =
  `businessImpactScore`/`avgOutcomeWinRate` from
  `intelligenceApi.businessImpact()`. Every card renders "—" honestly when
  its source has no data yet, never a fabricated number.
- **Backend permission fix (same pattern as Phase 1 decision #1)**: `GET
  /api/admin/intelligence/knowledge-graph` switched from `require_admin` to
  `require_org_member` in `backend/app/routers/admin_intelligence.py` — the
  KNOWS pillar needs this to be reachable by real, non-admin org members.
  Confirmed via direct code read of
  `knowledge_graph_service.get_admin_summary()` (lines 478-522) that this
  endpoint returns aggregate counts/type-lists only (`entity_count`,
  `relationship_count`, `entity_types`, `relationship_types`,
  `avg_relationship_confidence`, `max_traversal_hops`) — no raw entity or
  relationship content. The adjacent `GET
  /api/admin/intelligence/knowledge-graph/traverse` endpoint (entity-by-id
  lookups) was deliberately left `require_admin` and unchanged.
- **New regression tests** in
  `backend/tests/test_admin_intelligence_overview_permissions.py`:
  `test_knowledge_graph_summary_reachable_by_non_admin_member` and
  `test_knowledge_graph_traverse_stays_admin_only`. Full file:
  **9/9 passed** (7 pre-existing + 2 new), confirmed by direct pytest run.
- **Verification**: `tsc --noEmit` clean across the whole `apps/web`
  workspace; `eslint` on every new/changed file — 0 errors. Existing
  frontend unit tests (`__tests__/intelligence/*`, 29 tests across 5 files)
  all still pass — no regressions. Pushed as `acff957c2929277bfd2ffcd2aeed8e37252e8407`.
  Confirmed live: Vercel deployment `dpl_BmSBi4PSFokyRc4ZaKWXeZdJ39Dd`,
  `readyState: READY`, `target: production`, aliased to `gravitre.app`,
  `githubCommitSha` matches exactly. Railway backend `GET
  https://api.gravitre.app/health` returns
  `git_sha: acff957c2929277bfd2ffcd2aeed8e37252e8407` — same commit, both
  layers live on the same tip.
- **Live browser verification**: authenticated `browser-use` pass against
  `https://gravitre.app/intelligence` (production, no login redirect,
  console errors = `[]`). All 5 pillar cards rendered with real values —
  Knows `0` / "0 relationships mapped", Learns `0` / "11 models tracked",
  Predicts `0` / "of 14 in catalog", Acts `0` / "Active runs, last 24h",
  Improves (see bug below). Layer 2 correctly showed the honest empty
  state ("Nothing ranked as urgent right now") for this org. Layer 3
  showed 3 real suggested questions from a live daily briefing for this
  org ("What agents are currently active?" / "Show failed workflows from
  today" / "Which connectors have sync errors?") — the example-question
  fallback disclosure correctly did *not* render, because this org has a
  real briefing (this is correct behavior, not a gap). Clicking a question
  chip navigated to `/ai?prompt=What%20agents%20are%20currently%20active%3F`
  and the assistant answered with real agent names (Sales Agent, Marketing
  Agent) and source citations — a genuine end-to-end pass through the same
  `/ai` surface. Pre-existing sections below (Model data readiness,
  GIBE Module C strip, routing/simulation cards, link groups) all
  confirmed present and unchanged.
- **Bug found by this same live pass, fixed same-session**: the Improves
  card showed `10000` (hint "healthy") instead of a sane 0-100 score. Root
  cause: `businessImpactScore` is already 0-100 server-side
  (`backend/app/services/business_impact_service.py`:
  `max(0, min(100, 100 - penalty))`), but the new component multiplied it
  by 100 again assuming a 0-1 fraction. `avgOutcomeWinRate` (used for the
  hint text) *is* a genuine 0-1 fraction and was scaled correctly — only
  `businessImpactScore` had the bug. Fixed in
  `apps/web/components/intelligence/intelligence-pillars.tsx`, pushed as
  `bc733d28bb7008752afd73fd5754ca424462172a`, confirmed `READY` on
  `gravitre.app` via deployment   `dpl_BnATqgdiKjYQUqeWxvkUunsKAPJv`
  (`githubCommitSha` matches). Re-verified live: a second authenticated
  `browser-use` pass on `/intelligence?cachebust=phase3verify2` confirmed
  the Improves card now shows `100` / "healthy" (was `10000`) — matches
  `businessImpactScore=100` for an org with zero penalties, `scoreLabel`
  "healthy" at `>=80`. Knows/Learns/Predicts/Acts unaffected by the fix,
  still `0` with the same honest hints as before.
- **Scrutiny applied to the live-verification claims** (same discipline as
  Phase 2.5's caught false-alarm): the subagent's first pass flagged the
  missing example-question disclaimer on the "Ask Gravitre" card as a
  potential gap. This is **not a bug** — the disclaimer is intentionally
  conditional (`usingFallback = !suggestions?.length`) and correctly did
  not render because this org has a real live daily briefing with 3 real
  suggested questions ("What agents are currently active?" / "Show failed
  workflows from today" / "Which connectors have sync errors?"), not the
  brief's example questions. Re-read the component source to confirm this
  before accepting the subagent's framing.
  Separately: showing `entityCount=0`/`relationshipCount=0` (an actual
  number, not the "—" honest-gap fallback) on the Knows card is itself
  proof the `GET /knowledge-graph` call returned `200` with real payload
  for this authenticated session — if the permission fix had not taken
  effect (or this session were unauthorized), the SWR fetch would have
  failed and the component's `!= null` check would have rendered "—"
  instead. **Caveat, stated honestly**: this proves the endpoint call
  succeeds end-to-end for *this* session; it does not by itself prove that
  session is a non-admin member (role wasn't independently confirmed via
  browser). The precise, authoritative proof of the admin-vs-member
  distinction is the backend pytest
  (`test_knowledge_graph_summary_reachable_by_non_admin_member`), which
  explicitly mocks `require_org_member` (not `require_admin`) and asserts
  `200` — that test is what actually isolates the permission tier; the
  live pass corroborates real end-to-end wiring on top of it.
- **Console errors**: none observed on `/intelligence` (checked via CDP
  `Log.enable`/`Runtime.enable`, empty array both passes) or after
  navigating to `/ai?prompt=...` from a Layer-3 chip click (real assistant
  reply with real agent names, confirming the deep-link pattern works).
- **Regression check**: pre-existing sections (Model data readiness —
  Ready `0`/Needs data `11`/Recent train `0`/Tracked `11`; GIBE Module C
  runtime-honesty strip; routing-trace/simulation cards; Measure/Models/
  Knowledge link groups) all confirmed present in the DOM snapshot,
  unchanged.

## No-invented-surfaces declaration

This document adds no code, no customer-facing price, claim, badge, or entitlement toggle. It is a proposal only. Every technical claim above is sourced to a specific file path, line range, or delivery-doc artifact gathered during this Phase 0 inventory (three parallel `explore` passes); nothing here is fabricated or assumed. Where data was insufficient to answer a §1 question honestly, that gap is stated explicitly rather than guessed.
