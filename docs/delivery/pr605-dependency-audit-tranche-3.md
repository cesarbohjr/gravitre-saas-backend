# PR #605 — Dependency audit tranche 3: model policy, tool readiness and runtime scale
Date: 2026-11-04. Source baseline: `557be844f191767ea51c9f1d1d4958e5b046ca53`. Static inspection only; active production call frequencies remain unverified.

## New source-backed findings
| ID | Priority | Evidence | Architectural gap or risk | Proposed engineering fix |
|---|---|---|---|---|
| ECO-016 | P0 | `backend/app/services/unified_turn_reasoning_service.py` (~142KB) | Unified turn owns its own `_resolve_unified_turn_model` and uses multiple `_mark_live_fallthrough` sites; potential divergence from organization-wide model policy and behavior based on fallthrough reasons. This is a **risk**, not proven policy bypass. | Trace actual model selection and authorization for text/voice/task modes. Introduce a shared typed model decision record, with provider, policy, cost, tool capability and reasoning requirements; test explicit overrides and failures. |
| ECO-017 | P0 | `backend/app/services/model_router.py` (~54KB) | Model router already integrates organization policy, provider adapters, circuit breaker and provider failover. A blanket removal of failover would risk availability and safety. | Preserve same-contract resilience, instrument provider selection/failover cause and enforce capability parity; prevent hidden downgrade to chat-only when tools are needed. |
| ECO-018 | P0 | `backend/app/services/chat_connector_execution_service.py` (~203KB) | Chat execution service already imports canonical connector availability and uses session state, write approvals, registry and tool execution. **Do not claim these are absent.** Large surface and multiple dependencies increase migration blast radius. | Build method-level call graph, identify orchestration vs execution responsibilities, add contract tests for tenant readiness, scope, cancellation and verified writes before decomposition. |
| ECO-019 | P1 | `backend/app/services/connector_execution_matrix.py` (~11KB) | Execution matrix synthesizes action catalog, registered tools and approval requirements. Catalog eligibility may differ from actual per-tenant readiness. | Keep static capability inventory separate from runtime tenant readiness, and require action-level executable availability before selection. |
| ECO-020 | P1 | `backend/app/services/conversation_memory_engine.py` (~8KB) | Memory engine depends on conversation-state service, but many additional memory modules exist. No proof yet of duplicate writes or dead code. | Trace memory writes/reads, authority, promotion, TTL, retrieval budget, privacy, cross-turn contamination and conversation isolation. |
| ECO-021 | P1 | `backend/app/services/workflow_execution_strategy.py` (~3.8KB) | Workflow execution maps results to ExecutionPlan/Observation, indicating an existing bridge rather than an entirely disconnected execution system. | Verify outcome status and approval semantics match canonical execution outcome across workflow, play and direct chat. |

## Dependency chains now identified (static)
- Unified LIVE reasoning → model router, tool registry, tool retrieval/narrowing, pending context, write gate, voice prompt composition and user-facing copy guard.
- Model router → organization model policy, OpenAI/Anthropic/Gemini adapters, provider tool router, failover/circuit breaker, guardrails and database client.
- Chat connector execution → connector availability, tool registry, action mapper, session state, approval evaluator, spoken write approval, notification emitter, conversation state, artifact serialization.
- Connector execution matrix → action catalog, action aliases, tool service, catalog write approval authority.
- Workflow execution strategy → ExecutionPlan, ExecutionStep, ExecutionObservation.

## Additional acceptance contracts
1. Model selection must honor tenant policy, explicit model pin, tool-call support, task complexity, and cost policy consistently across all surfaces; test disabled provider and provider failure.
2. Connected tool must be both catalogued and tenant-executable, with scope, approval, and live action result verified; distinguish proposed action vs completed action.
3. Read, write, approval, cancellation and interrupted-stream transitions preserve a single durable execution state and do not generate contradictory final answers.
4. Provider failover is allowed only if tool and safety contract are preserved; record actual chosen provider and why.
5. Memory cannot silently overwrite verified tool outcomes or mix tenants; maintain source provenance and temporal relevance.

## Audit limits
This tranche verifies source structure and imported dependencies. It does **not** establish runtime call frequency, deployed environment flags, dynamic imports, database migration correctness, full tertiary wiring, live tool/voice behavior or CI pass status. No deletion authorization or completed-audit claim.
