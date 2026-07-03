# Phase E — Long-Horizon Learning (binding spec)

Status: **Complete** for shipped components (2026-07-03).  
World models, neural RL, and federated learning remain **explicitly gated** — not partial stubs.

---

## Component status matrix

| Component | Status | Runtime behavior |
|-----------|--------|------------------|
| **Tabular ledger v2 (UCB)** | **LIVE** | `StrategyPerformanceLedger.choose_preferred_strategy()` uses win-rate then UCB; wired through `ModelSelector` |
| **Memory conflicts** | **LIVE** | `detect_agent_memory_conflicts()` at retrieval; org admin scan; SSE `memoryConflicts` |
| **World models** | **PLANNED** | `WorldModelScaffold.check_activation_status()` — auto checklist; substitute: simulation + dependency impact |
| **Neural RL** | **PLANNED** | Disabled unless `GRAVITRE_NEURAL_RL_SIGNOFF=approved` |
| **Federated learning** | **DISABLED** | Legal + FL infra prerequisites documented; per-org training only |

---

## Tabular ledger v2 (complete)

### Algorithm

1. Rank strategies by empirical win-rate when `decided_samples >= 20` and win-rate beats default by `>= 0.05`.
2. Else UCB1 exploration: `exploitation + sqrt(2 * ln(N) / n)` when `decided_samples >= 5`.
3. Apply org segment weights from `org_learning_profile_service`.

### Storage

Table: `strategy_performance_records`  
Fields: `strategy_key`, `outcome_polarity` (win/loss/neutral), `segment_key`, metadata.

### API surfaces

| Endpoint | Payload |
|----------|---------|
| `GET /api/admin/intelligence/learning/bandit-status` | `active_bandit_version`, `summary.top_strategies[].ucb_score`, `phase_e_status: complete` |
| `GET /api/admin/intelligence/learning/live-dashboard` | `bandit` + `long_horizon` manifest |

### UI

`BanditStatusCard` — win/loss/win-rate/**UCB** table on Admin → Intelligence → Overview.

---

## Memory conflicts (complete)

### Detection

`detect_agent_memory_conflicts(memories)` uses opposing-sentiment pairs via `context_conflict_detection._has_opposing_sentiment`.

### Surfaces

| Surface | Path |
|---------|------|
| Task retrieval | `build_task_retrieval_context` → `memory_conflicts` in context JSON |
| Orchestrator | Injected as `<memory_conflicts>` context source when non-empty |
| Assistant SSE | `memoryConflicts` on `data-intelligence` chunk |
| Admin scan | `GET /api/admin/intelligence/learning/memory-conflicts` |
| Live dashboard | `memory_conflicts` block with counts |

### UI

`MemoryConflictsCard` on Admin → Intelligence → Overview.

---

## World models (PLANNED — honest gate)

Activation requires **all**:

1. `500+` measured outcomes in `agent_action_outcomes`
2. `causal_impact_analyzer` status TRAINED
3. `WORLD_MODEL_ENABLED=true`

Until met: returns `not_available` with prerequisite progress — never fake inference.

Substitute: `dependency_impact_service` + `SimulationService`.

---

## Neural RL (PLANNED — sign-off gate)

- Default: **off**
- Enable only when `GRAVITRE_NEURAL_RL_SIGNOFF` ∈ `{approved, true, 1, yes}`
- Tabular v2 remains default policy even when sign-off granted (neural path is future work)

---

## Federated learning (DISABLED)

`FederatedLearningCoordinator` returns `{ status: disabled }` with documented prerequisites:

1. Legal review + customer consent
2. Flower or equivalent FL library
3. Differential privacy
4. Secure gradient aggregation
5. Minimum 100 participating orgs

Marketplace **federated connector grants** (read-only cross-org) are unrelated to ML federated training.

---

## Policy manifest service

`get_long_horizon_status(org_id)` in `long_horizon_policy_service.py` — single source for admin dashboards and docs.

---

## Acceptance criteria (Phase E complete)

- [x] UCB scores in ledger admin summary
- [x] Model selection uses bandit v2 with `bandit_version: v2`
- [x] Memory conflicts at retrieval + admin API + SSE
- [x] Admin UI cards for bandit + conflicts
- [x] World models / neural RL / federated explicitly PLANNED or DISABLED in manifest
- [x] `phase_e_status: complete` in `get_rl_policy_status()`

---

## File index

| File | Role |
|------|------|
| `backend/app/services/strategy_performance_ledger.py` | UCB + admin summary |
| `backend/app/services/rl_policy_gate.py` | Neural RL sign-off + phase status |
| `backend/app/services/long_horizon_policy_service.py` | Component manifest |
| `backend/app/services/agent_memory_service.py` | Conflict detect + org scan |
| `backend/app/routers/admin_intelligence.py` | bandit-status, memory-conflicts, live-dashboard |
| `backend/app/services/intelligence_orchestrator.py` | Context + turn metadata |
| `backend/app/operators/assistant_sse.py` | SSE trust fields |
| `apps/web/.../bandit-status-card.tsx` | UCB UI |
| `apps/web/.../memory-conflicts-card.tsx` | Conflicts UI |

---

## References

- Foundation stack v3–v6: [`INTELLIGENCE_ENGINE_V3_V6_TABLES.md`](INTELLIGENCE_ENGINE_V3_V6_TABLES.md)
- Bandit ladder v3–v6 (UCB): [`BANDIT_V3_V6_TABLES.md`](BANDIT_V3_V6_TABLES.md)
- Universal intelligence waves: [`UNIVERSAL_INTELLIGENCE_LAYER_SPEC.md`](UNIVERSAL_INTELLIGENCE_LAYER_SPEC.md)
