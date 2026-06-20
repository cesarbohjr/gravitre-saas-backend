# Universal Intelligence Layer — Phase 3 Spec (binding)

Status: **Approved for implementation** (2A default path).  
Last updated: 2026-06-07.

Binding inputs: Phase 1 fragmentation map, Phase 2 maturity assessment, human decisions below.

---

## Human decisions (locked)

| # | Decision | Outcome |
|---|----------|---------|
| **2** | Orchestration convergence | **2A ships as default.** CoordinationLayer built behind internal flag only; forced cut-over or kill at end of evaluation window. |
| **3** | External claims | **Strict, effective immediately.** No maturity-ladder numbers in customer-facing material until `execution_mode` is user-visible and Swarm trust fix has shipped. |
| **1** | Canonical workflow engine | **APPROVED (1A)** — `execute.py` entry façade; `execution_engine_runtime` / `execute_workflow_graph` canonical. Linear: [STA-259](https://linear.app/staqbot/issue/STA-259). Blocks migration step 7 only. |

---

## Architecture overview

```
IntelligenceOrchestrator (facade)
├── 1. Intent + routing
├── 2. UnifiedRetrievalService          ← migration step 1 (in progress)
├── 3. Confidence + grounding
├── 4. Plan resolution + persona       ← two modes (this spec)
├── 5. ExecutionCore + profile         ← 2A default (AgentIntelligence / ReAct)
└── 6. Output + execution_mode

CoordinationLayer (internal flag only — not 2A default)
├── ParallelFanout      (Swarm pattern)
├── CouncilAggregate    (AgentCouncilService pattern)
└── SequentialContext   (workflow step_outputs / handoff pattern)
```

---

## Step 4 — Plan resolution + persona (two modes)

Step 4 is **not** a single “always generate a plan” step. It branches on whether a plan already exists before the run executes.

### Mode enum

```python
class PlanResolutionMode(str, Enum):
    RESOLVE_EXISTING = "resolve_existing"   # bind pre-defined work unit
    GENERATE_AT_RUNTIME = "generate_at_runtime"  # ReAct / structured planning
```

### `RESOLVE_EXISTING`

Use when decomposition happened **before** this orchestrator invocation.

| Caller | Plan source | Orchestrator behavior |
|--------|-------------|------------------------|
| **Workflow run** | `definition_snapshot.steps` or `graph.nodes/edges` + current step/node id | Load step definition, task string, config; apply agent persona from step metadata; **do not** LLM-decompose the workflow |
| **Swarm subtask job** | `subtask_prompt`, `scoped_tools`, swarm `objective` from job payload | Bind subtask spec; apply sub-agent persona; **do not** re-decompose objective into new subtasks |
| **Workflow agent step (handoff)** | Step task + optional `briefing_from_steps` built from `step_outputs` | Merge upstream briefing into prompt context; persona from assigned agent |

**Outputs of this mode:** `ResolvedPlan` — `{ mode, work_unit_id, task_text, persona_key, permitted_tools?, upstream_context?, metadata }`

### `GENERATE_AT_RUNTIME`

Use when no pre-existing decomposition is supplied.

| Caller | Orchestrator behavior |
|--------|----------------------|
| **Operator job** (`operator_task`) | Persona from operator/agent record; plan emerges via ReAct loop + structured result |
| **Single agent** (`run_agent_task`) | Same as today’s `AgentIntelligence.execute_task` |
| **Assistant `run_agent_task` tool** | Delegates to GENERATE_AT_RUNTIME with advisory or executing profile per tool config |

**Outputs of this mode:** plan/trace produced by ExecutionCore (ReAct trace, recommended_actions, tool_calls).

### Persona (shared across both modes)

Persona application is **orthogonal** to plan resolution:

- Load from `agent.config.persona`, operator role, or synthetic agent builder
- Applied **after** plan binding/generation, before ExecutionCore invocation
- Same `build_agent_system_prompt()` path as today

### Routing table (default 2A)

| Surface | Step 4 mode | Step 5 profile |
|---------|-------------|-----------------|
| Workflow step (`invoke_tool`) | RESOLVE_EXISTING | Deterministic handler (not ReAct) |
| Workflow step (`agent`) | RESOLVE_EXISTING | REACT_EXECUTING |
| Swarm subtask (post trust-fix) | RESOLVE_EXISTING | REACT_EXECUTING (scoped tools) |
| Operator async job | GENERATE_AT_RUNTIME | REACT_EXECUTING |
| Single agent task | GENERATE_AT_RUNTIME | REACT_EXECUTING |
| Assistant chat | N/A (no Step 4 decomposition) | STREAMING_ADVISORY |
| Knowledge Search | N/A | RETRIEVAL_ONLY |

### API sketch

```python
@dataclass
class PlanResolutionRequest:
    surface: str  # workflow | swarm | operator | agent | ...
    org_id: str
    # RESOLVE_EXISTING
    existing_plan: dict | None = None
    step_outputs: dict | None = None
    subtask_spec: dict | None = None
    # GENERATE_AT_RUNTIME
    task_text: str | None = None
    agent: dict | None = None

def resolve_plan(req: PlanResolutionRequest) -> ResolvedPlan:
    if req.existing_plan or req.subtask_spec or req.step_outputs is not None:
        return _resolve_existing(req)
    if req.task_text:
        return _wrap_runtime_generation(req)
    raise PlanResolutionError("cannot resolve plan")
```

CoordinationLayer prototype uses the **same Step 4 branch** — only Step 5+ coordination differs when flag is on.

---

## 2A — Default production path (ships now)

Customer-facing production runs **only** this stack until CoordinationLayer evaluation completes.

### In scope

1. **UnifiedRetrievalService** — consolidate 5 retrieval paths (migration step 1)
2. **ExecutionCore** — extend `AgentIntelligence` as orchestrator execution core
3. **Dual execution profiles** — `STREAMING_ADVISORY`, `REACT_EXECUTING`, `RETRIEVAL_ONLY`
4. **`execution_mode` visibility** — every intelligence run emits and UI surfaces:
   - `tools_executed` | `advisory_only` | `degraded`
   - `tools_available`, `tool_call_count`, `execution_verified`
5. **Swarm trust fix** — `run_swarm_subtask_job` → ExecutionCore (ReAct + scoped tools), retroactive `execution_verified=false` on existing rows

### Out of scope for 2A (unchanged customer behavior)

- Swarm UI / Workflow UI behavior changes from CoordinationLayer flag
- Runtime LLM decomposition of swarm objectives (caller still supplies subtasks)
- Level 6 outcome loops
- Workflow engine pick (decision 1)

### Swarm trust fix (P0 within 2A)

- Replace `ModelRouter.complete` JSON-only path with `ExecutionCore` + `RESOLVE_EXISTING`
- Migration: `execution_verified boolean NOT NULL DEFAULT false` on swarm tables; backfill all existing rows
- UI label: **Suggested — not verified** until `execution_verified=true`

---

## CoordinationLayer — internal validation only

Not a customer-facing choice. Not a permanent toggle.

### Flag

- Name: `coordination_layer_enabled` (org-level or env override)
- **Allowed orgs:** internal test orgs + synthetic smoke org only (e.g. `00000000-0000-0000-0000-000000000001`)
- **Never** enabled for real customer orgs in production UI
- When off (default): swarm/workflow use 2A paths (post-hoc council, sequential `step_outputs`)

### Components (prototype)

| Component | Source pattern | Flag-on behavior |
|-----------|----------------|------------------|
| `ParallelFanout` | `start_swarm` job enqueue | Optional alternate fan-out scheduler |
| `CouncilAggregate` | `AgentCouncilService` | Shared-context-aware aggregation vs post-hoc only |
| `SequentialContext` | workflow `step_outputs` + handoff briefing | Live context channel for swarm subtasks (L4 probe) |

### Start condition

**Do not begin CoordinationLayer prototype until ExecutionCore + Step 4 branch are stable on 2A** (after Swarm trust fix lands). Building on a moving foundation is explicitly out of scope.

### Evaluation window

- **Start:** date 2A deploy completes in production (ExecutionCore + Swarm trust fix + `execution_mode` backend fields)
- **End:** **6 weeks** after that date (hard cap; recommend recording as `coordination_layer_decision_due` in Linear)
- **Example:** if 2A ships 2026-07-07 → decision due **2026-08-18**

During window:

- Run paired scenarios on internal test data (same objective/subtasks, flag off vs on)
- Compare outputs: L4 coordination quality, council outcomes, latency, failure modes
- Track **actual** dual-path maintenance cost (PRs, incidents, test duplication)

### Forced outcomes (exactly one)

1. **Cut over** — delete 2A swarm/workflow coordination duplicates; CoordinationLayer becomes sole path; remove flag.
2. **Kill** — delete CoordinationLayer code and flag; do not leave dormant.
3. **Extend once** — only with a **named blocking question** documented in writing; max one extension; no open-ended renewals.

**Binding:** no indefinite dual-path orchestration.

---

## Migration sequence

| Order | Work | Depends on | Customer impact |
|-------|------|------------|-----------------|
| **1** | UnifiedRetrievalService | — | None (internal swap) |
| **2** | Step 4 `resolve_plan` + wire into ExecutionCore | 1 | None |
| **3** | `execution_mode` on AgentResult + Operator/agent job UI | 2 | Visibility |
| **4** | Swarm trust fix + retroactive migration | 2 | Trust labels |
| **5** | Assistant → unified retrieval; keep STREAMING_ADVISORY | 1 | None |
| **6** | Knowledge Search → unified retrieval backend | 1 | None |
| **7** | Workflow consolidation | **Decision 1** | TBD |
| **8** | CoordinationLayer prototype | 2–4 stable | Internal only |

Steps 1–4 are **2A**. Step 8 only after 2A stable.

---

## External claims policy (Strict — immediate)

### Rules

- **No** maturity-ladder labels (`Level 5`, `L5-capable`, etc.) in demo scripts, sales decks, landing copy, changelog, or docs aimed at prospects until:
  1. `execution_mode` is **user-visible** in product UI, and
  2. Swarm trust fix has **shipped**
- Prefer factual language: *“Supports connector actions when integrations are connected; per-run verification shown in UI”* (once UI ships)

### Audit (2026-06-07)

**Literal “Level 5” / ladder language:** not found in repo marketing or docs.

**Overclaims that violate Strict intent (need edit):**

| Location | Copy | Issue |
|----------|------|-------|
| `apps/web/app/(marketing)/changelog/page.tsx` | “Shared memory between collaborating agents”, “real-time” | Implies L4 not present in swarm today |
| `apps/web/app/(marketing)/changelog/page.tsx` | “multi-agent orchestration”, “10x faster execution” | Unverified superlatives |
| `apps/web/app/(marketing)/blog/page.tsx` | Same 2.0 release excerpt | Same |
| `apps/web/app/(marketing)/features/page.tsx` | “Multi-agent orchestration”, “Real-time task execution”, “take actions across all your tools” | Overstates verified execution |
| `apps/web/app/(marketing)/page.tsx` | “take actions automatically” | Should be conditional on connected integrations + verification |
| `apps/web/app/(marketing)/docs/[...slug]/page.tsx` | Operator “executes complex workflows automatically” | Overstates default operator path |

**Action:** product/marketing owner should schedule immediate copy review; engineering tracks via `execution_mode` + Swarm fix ship gates.

---

## Open items

- [x] **Decision 1** — workflow engine 1A approved ([STA-259](https://linear.app/staqbot/issue/STA-259))
- [ ] Record 2A production ship date → set CoordinationLayer decision due date on [STA-258](https://linear.app/staqbot/issue/STA-258)
- [x] Marketing copy draft — see [`MARKETING_COPY_STRICT_POLICY_REVIEW.md`](MARKETING_COPY_STRICT_POLICY_REVIEW.md) (pending product/marketing approval)

## CoordinationLayer decision gate

| Field | Value |
|-------|-------|
| Linear | [STA-258](https://linear.app/staqbot/issue/STA-258) |
| Owner | **Cesar Bohorquez Jr.** (`coordination_layer_decision_owner`) |
| Due | `coordination_layer_decision_due` = **2026-08-18** |
| Outcomes | Cut over \| Kill \| Extend once (named reason) |

---

## References

- Phase 1: `docs/delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md`
- Phase 2 maturity: conversation transcript / audit notes
- Linear backlog: `docs/ai/LINEAR_AI_INTELLIGENCE_BACKLOG.md`
