# Unified agent eval + per-run observability inventory (2026-09-03)

Standing inventory of **real, existing** batteries and audit-trace mechanisms.
This is the foundation to unify — not replace.

## Phase 0 verdict

Many individually rigorous batteries exist. **No single suite** runs across all
agents on every relevant change. **No single joined console** exists for a real
agent/workflow run. Closest shards: `/runs/[id]`, `/audit`, Admin Golden Signals,
Cognitive Turns, BusinessOutcome, chat explainability.

## A. Standing pytest / CI batteries (merge-blocking via `ci.yml`)

| Battery | Path | Covers |
|---------|------|--------|
| NL variance + withhold_no_tool (F1/F3/F10) | `backend/tests/services/test_routing_nl_variance_battery.py` | MSP enrich / list-create variance + BFCL-style withhold |
| Meta no-research | `backend/tests/services/test_meta_capability_no_research_battery.py` | Capability Qs never invent external research |
| F10 fallthrough enum | `backend/tests/services/test_unified_turn_fallthrough_enum.py` | Exhaustive fallthrough reasons |
| F1 retrieve-before-generate | `backend/tests/services/test_retrieve_plan_gate.py` | Pack miss → clarify / block_fabrication |
| F6 membership | `backend/tests/services/test_f6_hubspot_follow_up_membership.py` | Collection population verify |
| F8 action schema lint | `backend/tests/connectors/test_action_schema_standard_lint.py` | Catalog when/why/examples |
| Dormant model-call guard | `backend/tests/test_no_dormant_model_calls.py` | AST zero-arg factory mis-calls |
| Narrowed-tools / G5 | `backend/tests/services/test_*narrowed_tools*.py`, `test_g5_*.py` | Tools stay narrowed |
| Cognitive regression | `scripts/cognitive-regression-suite.mjs` | Kernel / pending-reply / council gates |
| Conversational behavior (unit) | `backend/tests/services/test_conversational_*.py` | Anti-fabrication / surface scorer |
| RAG / knowledge fabric | `backend/tests/rag/**`, `backend/tests/knowledge_fabric/**` | Hybrid RAG, CRAG, tool retrieval |
| Audit instrumentation | `backend/tests/**/test_audit_*.py` | `audit_events` write path |
| Department packs (unit) | `backend/tests/marketplace/test_{marketing,sales,finance,hr_talent,msp,cs,prospecting}_pack*.py` | Pack schemas / install / actions |
| Agent Security Gateway | `backend/tests/services/test_agent_security_gateway.py` (if present) / `backend/app/services/agent_security_gateway.py` | Knowledge is data; policy is authority |
| Clio / Legal tooling | `backend/tests/services/test_clio_tools.py` | Legal vertical actions (no Legal Intelligence Pack yet) |

## B. Live / scheduled batteries (not merge-blocking)

| Battery | Path | Cadence |
|---------|------|---------|
| Pending-reply / conversational / persona / injection | `scripts/verify-*-live.py` via `unified-turn-standing-batteries.yml` | Weekly |
| MSP enrichment workflow | `scripts/smoke-msp-enrichment-workflow-live.py` | Path CI |
| Phase4 pack live smokes | `scripts/smoke-phase4-*-pack-live.py` | Manual |
| STA-313 rerank eval | `scripts/eval-knowledge-rerank.py` | Manual |
| Chat E2E live | `scripts/smoke-chat-e2e-scenarios.py --live` | Manual |
| Production hardening | `production-hardening-smoke.yml` | Nightly |

## C. Observability shards (reuse, do not fork)

| Shard | Store / API | UI |
|-------|-------------|-----|
| Workflow run spine | `workflow_runs` + `workflow_steps` via `GET /api/runs/{id}` | `/runs/[id]` |
| BusinessOutcome | projector over run | Completed work panel |
| Tool / execute audits | `audit_events` / `audit_logs` via `write_audit_event` | `/audit` |
| Cognitive turn traces | `cognitive_turn_traces` via `/api/admin/cognitive-turns` | Admin Intelligence |
| Golden signals | aggregates over `audit_events` | Admin Golden Signals |
| Chat explainability | turn envelope | Assistant panels |
| ReAct job traces | `result.react_trace` | Agent job clients |
| Model cost / latency | `model_calls`, audit `latency_breakdown` | Sparse on run detail today |

## D. Gaps this program closes

1. **Unified department eval suites** — Marketing, Sales, Finance, Legal (Clio vertical), HR, MSP — covering knowledge, retrieval/citation posture, calculation, tool selection, permissions, action correctness, injection resistance, hallucination/withhold, honest refusal — CI-gated on pack/tool/knowledge path changes.
2. **Joined per-run observability console** — one view on `/runs/[id]` joining existing APIs/stores (no new logging system).

## E. Explicit non-goals

- Do not invent a parallel `observability_events` table.
- Do not claim Legal Intelligence Pack exists (it does not); Legal suite uses Clio tooling + permission/security gates.
- Do not invent customer-facing prices, badges, or Enable toggles.

## Shipped (2026-09-03)

### Phase 1 — department eval suites

- Registry: `backend/app/services/department_eval_registry.py` (Marketing, Sales, Finance, Legal/Clio, HR, MSP)
- Consolidated tests: `backend/tests/eval/test_department_eval_suites.py`
- Runner: `scripts/run-department-eval-suite.py`
- CI gate: `.github/workflows/department-eval-suites.yml` (path-triggered on pack/RAG/tool/eval changes)

### Phase 2 — joined per-run observability

- Service: `backend/app/services/run_observability_service.py` (joins `workflow_runs`/`workflow_steps`, `audit_events`, `cognitive_turn_traces`, `intelligence_outcome_events`; strips private CoT)
- API: `GET /api/runs/{run_id}/observability`
- UI: `RunObservabilityConsole` on `/runs/[id]`

### Verification (local)

- `pytest tests/eval/test_department_eval_suites.py tests/services/test_run_observability_service.py` → **32 passed**
- Bad-change gate: fake system `not_a_real_connector_xyz` fails the same pack/system assertion MSP CI uses (`BLOCK_PROOF_PASS`)
