# One Brain / CognitiveTurnKernel — phase evidence checklist (2026-08)

**Rule:** Local pytest / file greps are **CODE**-proven only. Labels PASS / done / working / fixed / shipped require an evidence pointer (audit_events timestamp+action, conversation/run id, CI URL, or prod log). Until then use **LIVE PENDING**.

Update by appending dated rows; do not erase prior evidence.

---

## Checklist

| # | Claim | How proven | Status | Evidence pointer |
|---|--------|------------|--------|------------------|
| 1 | Kernel module + planner + migration exist | File presence (`cognitive_turn_kernel.py`, `cognitive_planner.py`, `20260813120000_cognitive_turn_kernel.sql`) | **CODE** | Repo paths; also `scripts/cognitive-regression-suite.mjs` |
| 2 | Streaming path calls `run_pre_act` before `apply_unified_turn_live` | String-order check in `execute_task_streaming` region | **CODE** | Regression suite + `agent_intelligence.py` |
| 3 | Unified turn accepts `cognitive_context=` | Grep `unified_turn_reasoning_service.py` | **CODE** | Regression suite |
| 4 | Extension bridge enters kernel | Grep `run_kernel_for_entry` in `extension_bridge_service.py` | **CODE** | Regression suite |
| 5 | Council enters kernel | Grep `run_kernel_for_entry` in `council_service.py` | **CODE** | Regression suite |
| 6 | Flag off → skipped stage | Unit test `test_flag_off_returns_skipped_stage` | **CODE** | `backend/tests/services/test_cognitive_turn_kernel.py` |
| 7 | `org_id` required when enabled | Unit test `test_org_id_required_when_enabled` | **CODE** | same |
| 8 | Pre-ACT stages RETRIEVE…GOVERN | Unit test `test_run_pre_act_stage_names_retrieve_through_govern` | **CODE** | same |
| 9 | Cross-org memory rows excluded | Unit test `test_cross_org_memory_rows_excluded` | **CODE** | same |
| 10 | Admin list traces API registered | Router `cognitive_turns` + `main.py` include | **CODE** | `GET /api/admin/cognitive-turns` |
| 11 | Metrics admin API (list/upsert/resolve) | Router `cognitive_metrics` + service helpers | **CODE** | `GET/PUT /api/admin/cognitive-metrics` |
| 12 | What-if simulation API (Module C honesty) | Router + `simulate_business_scenario` | **CODE** | `POST /api/admin/cognitive-simulation/what-if` |
| 13 | Admin UI Cognitive turns tab | `cognitive-turns-tab.tsx` + `SURFACE_COPY.adminTabs.cognitive` | **CODE** | `/admin/intelligence` tab |
| 14 | CI runs cognitive regression suite | `.github/workflows/ci.yml` step | **CODE** | Workflow step name "Cognitive regression suite" |
| 15 | Migration applied in target Supabase | Remote table existence query | **PASS** | `information_schema` @ smyeexlrqdpymwjmgzqu lists `cognitive_turn_traces`, `org_metric_definitions`, `org_field_permissions`, `org_knowledge_nodes` after `apply_migration` cognitive_turn_kernel (2026-08-13) |
| 16 | Prod chat turn persists `cognitive_turn_traces` row | Prod query after Railway tip | **PASS** | `turn_id=02beb5fd-fdc4-421e-8fc0-603ee62c9889` @ `2026-08-13T09:27:12.654717Z` surface=`ai_chat` conversation_id=`9db0616b-3a40-4286-9af9-a725e04be8ea` |
| 17 | Streaming LIVE turn shows kernel stages then ACT | Trace stages + prod git_sha | **PASS** (ai_chat) | Stages RETRIEVE→RECALL→KNOWLEDGE→PLAN→VERIFY→GOVERN on turn above; prod `/health` `git_sha=0958772c…` @ `2026-08-13T09:32:21Z`; Railway run [31686266171](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31686266171) |
| 18 | Extension enrich path records kernel stage | Ops smoke + enrich turn_id | **PASS** | `cognitiveTurnId=08b5e50e-4ee0-4765-b8bd-b7a5def92df4` (probe `onebrain-141fd47471`) @ tip `88a04469` |
| 19 | Council turn records kernel stage | Ops smoke council surface | **PASS** | `turn_id=6d64364a-7c8e-4b3c-8b7f-d96599523c1c` surface=`council` |
| 20 | Metric upsert + resolve round-trip in prod org | Dual-agent resolve same id | **PASS** | `definition_id=cc33a9f3-93cc-4b8d-90b1-2853c9d323f0` metric_key=`arr_onebrain` agents A/B identical |
| 21 | Distinct `agent_chat` / `voice` traces | Ops smoke | **PASS** | agent `6470f0d2…`, voice `d87e0654…` stages RETRIEVE→GOVERN |
| 22 | Cross-org isolation (zero foreign rows) | Ops smoke RECALL pack | **PASS** | turn `b683f4c3…` leaked_marker=false foreign_org_rows_in_pack=0 vs foreign_org `658c76b3…` |
| 23 | Field-deny GOVERN + audit | Ops smoke + audit_events | **PASS** | `cognitive.govern.field_acl_deny` audit_id=`68b1461c-c6b8-47f5-9c4c-bb37254af2da` @ `2026-08-13T10:07:11.088726Z`; turn `4a5ac15e…` |
| 24 | Outcome→PLAN bias after failure | Ops smoke closed loop | **PASS** | recommendation_id=`2ad66e6c…`; PLAN `outcome_bias` notes include `failed_negative_decline` on probe; turn `81aa4ecc…` |
| 25 | Mode A bias reaches LIVE/classical prompts | Ops smoke `outcome_loop.prompt_injected` on tip `f33798ff` | **PASS** | tip `f33798ff2d65863144e1708a751074149dedbfb4`; `recommendation_id=5df90af5-cbf5-4198-986b-d9231b4691c5` event `recommendation_rejected`; turns `7e3537ec…`→`cf74e1bd…`; `prompt_injected=true`; artifact `one-brain-live-residuals.json` @ `2026-08-13T18:10:50Z` |
| 26 | Shared explainable pre-action card (chat + Approvals) | Shared `PreActionCard` + evaluator field stamps | **CODE** | ship `aad7af6d` on `main` (prod tip `3f9454be` includes it); vitest `__tests__/lib/pre-action-card.test.ts` 3 passed; LIVE PENDING — needs a fresh connector write confirm / Approvals row with `context.risk_level` |
| 27 | Phase A: novel pending phrasing → LLM fallback | Live classify probe on tip `42c66f92` | **PASS** | `phase-a-novel-pending-classify-live.json` @ `2026-08-13T20:57:49Z` probe `phasea-4dff8d8494`; both novel phrases `fast_path=null`, `final_intent≠confirm` |
| 28 | Phase B: council synthesis cross-exam | Live council on tip `42c66f92` | **PASS** | `phase-b-council-synthesis-live.json` @ `2026-08-13T20:59:49Z`; session `a0c2520f…`; `has_synthesis=true`; disagreement_trail length 2 |

---

## How to promote a row to PASS

1. Merge → Railway redeploy (backend) / Vercel (web) as applicable.
2. Exercise the live path once.
3. Record: timestamp + action (or turn_id / conversation_id / CI run URL).
4. Append under **Live evidence log** below; flip the row status to **PASS** with that pointer.

---

## Live evidence log

### 2026-08-13 — ship tip + schema

- CODE ship — `git_sha=0958772c` pushed `main` (`feat(cognitive): ship CognitiveTurnKernel path-unify + Phases 1–9 scaffold`); evidence stamp tip `b34477b2`
- PASS #15 — Supabase prod project `smyeexlrqdpymwjmgzqu`: tables `cognitive_turn_traces`, `org_metric_definitions`, `org_field_permissions`, `org_knowledge_nodes` present after migration
- CODE — `node scripts/cognitive-regression-suite.mjs` → PASS; `pytest tests/services/test_cognitive_turn_kernel.py` → 4 passed
- CODE — what-if honesty envelope: `confidenceSource=heuristic`, `confidenceIsEstimate=true`, `isFact=false` (local `simulate_business_scenario`)
- Deploy — Railway backend production **success** [31686266171](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31686266171) for `0958772c`; prod health `git_sha=0958772cfe324033073a78e56c62498af0b398c5` @ `2026-08-13T09:32:21Z`
- PASS #16/#17 — live `ai_chat` kernel pre-ACT: `turn_id=02beb5fd-fdc4-421e-8fc0-603ee62c9889` @ `2026-08-13T09:27:12.654717Z` stages RETRIEVE→GOVERN (`fabric_count=6`), conversation `9db0616b-3a40-4286-9af9-a725e04be8ea`
### 2026-08-13 — residual LIVE PASS (ops smoke)

- Tip — prod `/health` `git_sha=03e8837342cb7945142bd13525b7287db01f077b` (prior full residual PASS also on `88a04469`)
- Artifact — `docs/delivery/one-brain-live-residuals.json` verdict **PASS** (latest probe `onebrain-158978d328`, isolated org `f07e57c0…`; earlier `onebrain-141fd47471`)
- Surfaces — agent_chat / voice / extension_enrich / extension_action / council / **job** all true in checks
- Job — turn `4896c6a8…` (first) and latest smoke `job_execute_task` true on tip `03e88373`
- Cross-org / metrics / field ACL / outcome→PLAN — PASS (see checklist rows 20–24; field audit `68b1461c…` @ `2026-08-13T10:07:11.088726Z`)

### 2026-08-13 — Mode A prompt wire LIVE PASS (Part C rank 2)

- Tip — prod `/health` `git_sha=f33798ff2d65863144e1708a751074149dedbfb4`
- Artifact — `docs/delivery/one-brain-live-residuals.json` verdict **PASS** (probe `onebrain-f160b6fe1d`)
- PASS #25 — `outcome_loop.prompt_injected=true`; after notes cite `recommendation_rejected`; turn_after `cf74e1bd-91dd-450d-a542-461e9a9b9068`; job stages include `LEARN` on `3512f096…`
- Honesty — bar is prompt-section + PLAN bias injection (not streaming-path assistant-text delta)

### 2026-08-13 — Rank 3 pre-action card CODE ship

- Ship — `aad7af6d` `feat(cognitive): unify explainable pre-action card on chat and Approvals`
- Prod tip after follow-on — `/health` `git_sha=3f9454be…` (ancestor includes `aad7af6d`)
- CODE — vitest `pre-action-card` mappers 3/3; UI mounts `PreActionCard` in chat connector confirm + Approvals detail; backend stamps `estimated_impact` / `risk_level` / `approval_reason` onto pending_task + approval context
- LIVE PENDING #26 — no fresh connector-write approval exercised yet to prove `context.risk_level` on a prod Approvals row / chat confirm DOM

### Final Part B residual (honest)

| Surface | Kernel intake in code? | Live composition re-test |
|---------|------------------------|--------------------------|
| Main/TRY chat (`execute_task_streaming`) | Yes — `run_pre_act` before LIVE | **PASS** — turn `02beb5fd…` |
| Agent / voice chat | Same streaming path; surface label differs | **PASS** — `6470f0d2…` / `d87e0654…` |
| Extension enrich/actions | Yes — `cognitive_entry_adapters` | **PASS** — `08b5e50e…` / `0bee573b…` |
| Council | Yes — evidence pack inject | **PASS** — `6d64364a…` |
| Jobs/swarm/handoff (`execute_task`) | Yes — kernel first | **PASS** — job turn `4896c6a8-4248-4384-b7c1-671ce5b41eb8` @ `2026-08-13T10:34:12.510007Z` stages RETRIEVE→GOVERN (`entry_point=execute_task`) |
| Meson | Plan adapter only (`meson_plan_adapter`); NL execution later hits kernel | N/A as NL brain |
| Workflow deterministic steps | GOVERN on writes via existing authority; agent nodes via `execute_task` | Covered by job path when agent nodes call `execute_task` |
