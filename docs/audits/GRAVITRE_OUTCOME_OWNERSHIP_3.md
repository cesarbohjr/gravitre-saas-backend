# GRAVITRE 3.0 — PROMPT TO VERIFIED OUTCOME / OUTCOME OWNERSHIP

**Status:** ACTIVE ENGINEERING PROGRAM  
**Baseline:** main `44429deaf5f74e4d97d5a64ebe144eb1f0b59a82`  
**Direction:** PRESERVE + CONVERGE. Do not create a second runtime.

## Product invariant

A user states the business outcome. Gravitre owns the work from understanding through verified completion.

```
PROMPT
→ UNDERSTAND
→ ACCEPT OWNERSHIP
→ RESOLVE CONTEXT
→ PLAN
→ SELECT CAPABILITIES
→ GOVERN
→ EXECUTE
→ OBSERVE
→ ADAPT / REPAIR
→ VERIFY
→ CONFIRM
→ DELIVER RESULT
→ LEARN
```

Execution is not completion. Approval is not completion. A provider HTTP success is not completion. A workflow reaching its final node is not completion. Gravitre may use **Done / Completed** only when the requested outcome has verification evidence appropriate to that outcome.

## Canonical resources

The planner may compose existing Connectors, Agents, Workflows, Plays, Knowledge Fabric, organizational memory, datasets, internet/research, ActionSpecs and governed writes. These are resources, not separate user-facing brains. They share task truth, governance, Observations and completion semantics.

## Outcome state contract

`REQUESTED → UNDERSTOOD → PLANNED → EXECUTING → EXECUTED → VERIFYING → VERIFIED → COMPLETED`

Legal side states: `AWAITING_APPROVAL`, `BLOCKED`, `PARTIALLY_COMPLETED`, `FAILED`, `OUTCOME_UNCERTAIN`, `RESUMABLE`.

**Forbidden:** `tool.invoke.completed → COMPLETED` without outcome verification.

## Verification contract

Every material write must define its verifier before execution where feasible.

Minimum verification evidence:
- provider/resource identity;
- expected postcondition;
- read-back or authoritative observation;
- verification timestamp;
- verifier/action used;
- match/mismatch evidence;
- unresolved exceptions.

For multi-step objectives, every required step must be terminal and the parent outcome must satisfy its success criteria before `COMPLETED`.

## Responsibility contract

After accepting an executable objective Gravitre continues until one of these is true:
1. verified outcome;
2. user approval/input is genuinely required;
3. authorization/connector access blocks progress;
4. safe bounded recovery is exhausted;
5. the requested outcome is impossible or cannot be verified.

A recoverable connector/tool failure is an internal replanning event, not automatically a user handoff.

## Response contract

The user-facing response leads with the business result, not the trace.

Allowed completion language:
- **Done / Completed:** verified outcome.
- **Executed; verification pending:** provider accepted action but outcome is not independently verified.
- **Partially completed:** some required success criteria remain.
- **Blocked:** external/user dependency prevents safe continuation.
- **Failed:** bounded recovery exhausted.
- **Outcome uncertain:** side effect may have happened and reconciliation is required.

## Initial audit findings

The current architecture already contains most required primitives: `execute_task_streaming`, CognitiveTurnKernel, ExecutionPlan, ActionSpec, PendingAction, Observations, action lifecycle verification, capability/resource resolution, Knowledge Fabric, workflows/Temporal, outcome events and Composer.

The main risk is **semantic convergence**, not missing primitives:
- workflow/agent paths must not bypass canonical Observation + verification semantics;
- successful connector invocation must never imply business completion;
- recovery/replanning needs one ownership contract;
- compound objectives need parent-level success criteria;
- final Composer claims must be mechanically bounded by outcome state;
- evidence must survive cross-modal/resume paths.

## Engineering phases

### O0 — Completion truth gate
Make verified outcome a mechanical prerequisite for completion claims across connector, workflow and agent paths.

### O1 — Objective + success criteria
Persist an explicit objective contract: requested outcome, constraints, required evidence, completion criteria and acceptable blockers.

### O2 — Capability composition
Audit planner access to connectors, agents, workflows, Plays, KF, memory, datasets and internet. Remove user-visible/manual orchestration where the runtime can resolve safely.

### O3 — Recovery ownership
Bounded retry, parameter repair, alternate eligible action/provider, token/auth diagnosis, reconciliation-before-retry for uncertain writes.

### O4 — Compound verification
Parent objective completes only when all required child outcomes are verified or explicitly waived by the objective contract.

### O5 — Result delivery
Composer renders result/evidence/exceptions/artifacts and cannot upgrade an unverified state to completed prose.

### O6 — Learning
Only verified/measured outcomes become eligible learning signals; API success alone is excluded.

### O7 — Outcome Ownership benchmark
Held-out end-to-end journeys across CRM, support, sales, marketing, research, knowledge, workflows, agents and cross-modal continuity.

## Release gate

A change is not Outcome-Ownership-ready until:
- exact-head CI is green;
- held-out ownership contract passes;
- no production prompt contains benchmark answers;
- live tenant writes are read-back verified;
- failure/recovery journeys are exercised;
- final claims match persisted state;
- production human acceptance proves representative end-to-end tasks.

## Benchmark seed classes

1. CRM segment/list creation + read-back.
2. Research accounts → enrich → CRM update → follow-up task → verify.
3. Diagnose stalled pipeline → propose/remediate authorized causes → verify.
4. Support SLA regression → investigate → execute safe remediation → verify.
5. Knowledge-grounded analysis requiring tenant docs + live provider data.
6. Workflow delegation with governed write and parent-level verification.
7. Agent delegation with artifact + provider side effect + evidence.
8. Connector validation failure → repair → retry → verify.
9. Timeout after possible write → reconcile before retry.
10. Text → voice → text continuation of the same owned objective.

The benchmark will expand to 100+ held-out scenarios after O0/O1 contracts are enforced.


## Internal adversarial audit — pass 1

### Findings remediated

**OO-P0-01 — canonical completion fanout trusted caller status.**  
A caller could submit `status=completed` to `finalize_execution_outcome` without explicit source verification. Fixed: canonical fanout coerces this to `verification_inconclusive` unless `metadata.verification.verified=true`.

**OO-P0-02 — conversational workflow/agent success could be narrated as Done.**  
Fixed: `ExecutionResult` separates provider/task success from `outcome_verified`; unverified success remains verifying and positive learning is withheld.

**OO-P0-03 — Composer guarded literal Done more strongly than paraphrased completion.**  
Fixed: completion-shaped paraphrases (completed/finished/created/all set/etc.) are mechanically rejected for unverified success envelopes.

**OO-P0-04 — compound ExecutionPlan could complete when consequential children merely returned success.**  
Fixed: write/workflow/agent-delegation children require `structured.verified=true` before parent completion.

**OO-P0-05 — ReAct could terminalize a consequential plan from successful observations or answer text without verification.**  
Fixed: consequential ReAct completion now requires verified child observations; answer text alone cannot prove an external side effect.

**OO-P1-01 — recovery semantics were distributed and did not expose one explicit reconcile-before-retry policy.**  
Added `outcome_recovery_policy`: uncertain mutations reconcile before retry; transient reads use bounded retry; exhausted retry may replan; auth/scope blocks rather than loops.

### Existing strengths retained

- Write-success verification catalog already declares follow-up entity, field, membership or accepted-async modes.
- Async write verification already protects multi-step workflows from mid-step terminalization.
- Outcome learning already separates tool-success observations from measured business-impact events.
- Cognitive outcome PLAN bias excludes tool-success events.
- Capability evidence planning already requires live-provider evidence for CEO/ops questions and prevents Knowledge Fabric from substituting for required live data.

### Still open before peer review

1. Wire canonical recovery policy into every relevant execution dispatcher rather than leaving it as contract-only.
2. Audit workflow worker terminalization and agent child completion for verification evidence propagation.
3. Audit all callers of `finalize_execution_outcome(status="completed")` and remediate legacy callers that lack verification metadata.
4. Expand capability composition beyond specialized CEO/ops evidence plans and prove connectors + agents + workflows + Plays + KF + datasets + internet can be selected as resources under one objective.
5. Add held-out Outcome Ownership benchmark scenarios and CI gate.
6. Run exact-head tests/CI and remediate regressions.
7. Produce Claude peer-review packet only after internal audit closes P0/P1 findings.
