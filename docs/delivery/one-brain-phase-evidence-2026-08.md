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
| 16 | Prod chat turn persists `cognitive_turn_traces` row | Prod query / admin UI after deploy | **LIVE PENDING** | Needs authenticated chat after Railway tip `0958772c` |
| 17 | Streaming LIVE turn shows kernel stages then ACT | Prod chat + audit / turn_id | **LIVE PENDING** | — |
| 18 | Extension enrich path records kernel stage | Prod extension request + trace | **LIVE PENDING** | — |
| 19 | Council turn records kernel stage | Prod council run + trace | **LIVE PENDING** | — |
| 20 | Metric upsert + resolve round-trip in prod org | Admin API against live DB | **LIVE PENDING** | Schema ready; no seeded customer metrics inserted |

---

## How to promote a row to PASS

1. Merge → Railway redeploy (backend) / Vercel (web) as applicable.
2. Exercise the live path once.
3. Record: timestamp + action (or turn_id / conversation_id / CI run URL).
4. Append under **Live evidence log** below; flip the row status to **PASS** with that pointer.

---

## Live evidence log

### 2026-08-13 — ship tip + schema

- CODE ship — `git_sha=0958772c` pushed `main` (`feat(cognitive): ship CognitiveTurnKernel path-unify + Phases 1–9 scaffold`)
- PASS #15 — Supabase prod project `smyeexlrqdpymwjmgzqu`: tables `cognitive_turn_traces`, `org_metric_definitions`, `org_field_permissions`, `org_knowledge_nodes` present after migration
- CODE — `node scripts/cognitive-regression-suite.mjs` → PASS; `pytest tests/services/test_cognitive_turn_kernel.py` → 4 passed
- CODE — what-if honesty envelope: `confidenceSource=heuristic`, `confidenceIsEstimate=true`, `isFact=false` (local `simulate_business_scenario`)
- Deploy — GitHub Actions: CI run `31686266141`, Railway backend production `31686266171` (watch for green before promoting #16–#19)
- **Not claimed PASS:** multi-surface chat/voice/extension parity, cross-org isolation live probe, dual-agent metric resolve, field ACL block audit event, closed-loop before/after recommendation change

### Final Part B residual (honest)

| Surface | Kernel intake in code? | Live composition re-test |
|---------|------------------------|--------------------------|
| Main/TRY/agent/voice chat (`execute_task_streaming`) | Yes — `run_pre_act` before LIVE | **LIVE PENDING** |
| Jobs/swarm/handoff (`execute_task`) | Yes — kernel first | **LIVE PENDING** |
| Extension enrich/actions/confirm | Yes — `cognitive_entry_adapters` | **LIVE PENDING** |
| Council | Yes — evidence pack inject | **LIVE PENDING** |
| Meson | Plan adapter only (`meson_plan_adapter`); NL execution later hits kernel | N/A as NL brain |
| Workflow deterministic steps | GOVERN on writes via existing authority; agent nodes via `execute_task` | **LIVE PENDING** |

Residual gaps: no authenticated prod chat turn_id yet proving `cognitive_turn_traces.stages` sequence; no deliberate cross-org memory probe audit row; no dual-agent ARR definition-id live match; no field-deny audit event. Code paths are wired; promote each LIVE PENDING row only with a fresh post-deploy pointer.
