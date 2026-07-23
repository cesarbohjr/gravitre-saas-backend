# Unified turn reasoning — Phase 0 map

Reference: program brief `gravitree-conversational-ai-technical-brief.md` (not present in-repo at audit time; requirements captured in the unified-turn program prompt).

Goal: one reasoning call per turn (conversation + pending context + native tool schemas) **before** any tool execution. Write governance unchanged.

---

## 1. Current pipeline stages (execution order)

| # | Stage | File | Primary functions | Decides | Passes to |
|---|--------|------|-------------------|---------|-----------|
| 0 | HTTP entry | `backend/app/routers/assistant.py` | `assistant_chat` | Auth, cache, ledger ingest | `AgentIntelligence.execute_task_streaming` |
| 1 | Stream orchestrator | `backend/app/operators/agent_intelligence.py` | `execute_task_streaming` | Routing tier, persona, mode | Classifiers / connector / ReAct |
| 2 | Parameter ledger (early) | `backend/app/services/parameter_ledger.py` | `ingest_message_slots`, `get_ledger` | Slot hints from user text | `task_state` |
| 3 | **Conversational turn gate** | `backend/app/services/conversational_turn_gate.py` | `heuristic_turn_shape`, `classify_turn_shape`, `should_offer_conversational_path` | conversational vs task vs mixed; social `category` | Early exit or trimmed `task_text` |
| 4 | **Module D phrase path** | `backend/app/services/conversational_reply_service.py` | `generate_conversational_reply`, `generate_social_ack` | User-visible non-task copy | SSE complete (no tools) |
| 4b | Expression banks | `backend/app/services/voice_expression_range.py` | `pick_expression`, `EXPRESSION_BANKS` | Deterministic phrase rotation | Used by conversational + some operator copy |
| 4c | Operator voice | `backend/app/services/gravitree_voice.py` | `format_operator_message`, `voice_system_prompt_section` | Persona/register for LLM + static operator strings | System prompts + blocked-path copy |
| 5 | Platform tasks | `backend/app/services/conversational_execution_service.py` | `process_turn` | Create agent/workflow intents | Pending confirm / collecting |
| 6 | Connector routing | `backend/app/services/connector_chat_routing.py` | `should_run_connector_preflight`, `run_connector_fallback_turn` | Orch vs governed connector vs defer ReAct | Orch or turn controller |
| 7 | **Pending-reply classifier** | `backend/app/services/pending_reply_classifier.py` | `has_pending_family`, `build_pending_snapshot`, `classify_pending_reply`, formatters | 7-way intent when pending | Hold/clarify/cancel/resume handlers |
| 8 | Turn controller | `backend/app/services/conversation_turn_controller.py` | `prepare_conversation_turn`, `run_connector_turn` | Shared Module B dispatch | `ChatConnectorExecutionService.process_turn` |
| 9 | Orchestration | `backend/app/services/chat_orchestration_service.py` | `process_turn`, `_plan_segment` | Multi-step plans | Same mapper + approval |
| 10 | **Chat action mapper** | `backend/app/services/chat_action_mapper.py` | `match_segment`, `plan_from_match`, `skip_reason` | Regex/phrase score → catalog action | `ConnectorActionPlan` |
| 11 | Workflow validation | `backend/app/services/connector_action_workflows.py` | `validate_connector_plan`, `format_capability_fallback_message` | Missing fields, capability gaps | `stage_awaiting_params` / blocked message |
| 12 | Inference / assignee | `connector_parameter_inference`, `resolve_assignee_disambiguation` | Field fill, assignee choice | Plan enrichment | Approval or execute |
| 13 | Execute (governed) | `chat_connector_execution_service.py` | `execute_plan` → `ToolRegistry.execute_tool` | Live invoke after confirm | Outcomes / Module A |
| 14 | **ReAct loop** | `backend/app/operators/react_engine.py` | `run_streaming`, `_execute_tool_call` | Multi-iteration tool reasoning | Fallback connector materialization |
| 15 | Copy guard (recent) | `backend/app/services/user_facing_copy_guard.py` | `finalize_user_facing_message` | Strip dotted catalog keys from operator copy | User-visible strings |

**Parallel path note:** ReAct already uses native tool calling (`get_tools_for_agent` + `narrow_tools_for_turn` in the agent stack). Governed chat still prefers mapper + validation for NL turns unless structured tool_calls exist.

---

## 2. Catalog action schemas vs native function calling

| Layer | Location | Role | LLM-native? |
|-------|----------|------|-------------|
| Catalog specs | `action_catalog/registry.py`, `vendor_definitions.py` | 681 actions / 76 vendors | Source of truth |
| Execution matrix | `connector_execution_matrix.py` | Chat-exposed, kind, approval flags | Filters tools |
| JSON Schema for tools | `action_parameters.py` → `parameters_for_action`, `schema_generator.py` | OpenAI `parameters` | **Yes** (inferred or explicit `input_schema`) |
| Dynamic tool specs | `chat_tool_bridge.py` → `build_dynamic_chat_tool_specs` | **679** registered invoke paths | **Yes** via `AgentToolSpec.to_openai_tool()` |
| Tool registry merge | `tool_registry.py` | 679 dynamic + 33 static platform tools | `get_tools_for_agent` / `get_available_tools` |
| Workflow validation | `action_workflow_schema.py`, `get_workflow_schema` | **182/182 writes** — required fields, labels | **No** — chat validation / ledger, not emitted as tool JSON |

**Conversion needed for unified turn:** No new schema format. Wire existing OpenAI tool defs. Optionally attach workflow field **labels** in the pending-context block (not as tool schema) for clarifying questions.

---

## 3. Pending state → unified-call context (not a classifier)

| Source | Fields | Today used by |
|--------|--------|----------------|
| `task_state.pending_task` | `status`, `type`, `params` (label, integration, invoke_action internal) | Pending-reply classifier, confirm flows |
| `parameter_ledger` | `slots`, `pending_missing` | `stage_awaiting_params`, `resume_awaiting_params` |
| `task_state.current_plan` | `goal`, steps | Orchestration hold / modify |
| `pending_hold_prompt` | flag | Unrelated-turn hold |

**Designed context block** (implemented in `unified_turn_pending_context.py`):

- Human action label (never dotted catalog key in user-facing model output instructions).
- Status family (`awaiting_params`, `awaiting_confirm`, …).
- Missing fields as workflow labels where available.
- Optional “last assistant asked …” snippet from recent history.
- Plan goal snippet when `current_plan` present.

Pending-reply **intent** is not computed separately in the new path; the model sees pending context and decides reply vs slot-fill vs tool call vs confirmation.

---

## 4. Catalog size and tool context strategy

| Metric | Count |
|--------|------:|
| Catalog actions | **681** |
| Matrix rows | **681** |
| Dynamic chat tools (registered) | **679** |
| Full OpenAI tool payload (all connected) | **Too large** for one call |

**Decision:** Use **retrieval per turn now**, not full catalog. Existing helper: `agent_platform_optimizer.narrow_tools_for_turn` (default **28** tools, max **10** per connector, token overlap + connector focus). Unified shadow uses the same narrowing with configurable `UNIFIED_TURN_SHADOW_MAX_TOOLS` (default 32).

Future: embedding-based tool routing at 600+ scale (brief semantic-tool-routing) can replace keyword scoring without changing write gates.

---

## 5. `catalog_write_authority` hook points (unchanged in new design)

| Surface | File : function | When |
|---------|-----------------|------|
| Matrix tagging | `connector_execution_matrix.py` | `catalog_action_requires_write_approval` on each row |
| ReAct invoke | `react_engine.py` → `react_write_gate.block_react_write_execution` | Before `execute_tool` |
| ReAct staging | `react_write_gate.materialize_react_write_approval_turn` | Pending approval message |
| Governed chat | `chat_connector_execution_service.process_turn` | `requires_approval` → `awaiting_confirm` before `execute_plan` |
| Orchestration | `chat_orchestration_service._plan_segment` | Step-level approval flags |
| Canvas | `canvas_write_gate.py` | `invoke_action_requires_write_approval` |

**Unified turn rule:** The new call may **propose** a tool + args only. Execution still flows through existing `execute_plan` / ReAct gate / approval — no new bypass.

---

## Phase 1 deliverable

- `unified_turn_reasoning_service.py` — single-call shadow runner (no user output, no tool execution).
- `unified_turn_pending_context.py` — structured pending summary.
- `module_d_unified_voice_spec.py` — **full Module D system instruction** (registers, knowledge boundaries, imperfect-input silence, drift self-check, few-shots) wired as the reasoning-call system prompt — not a post-hoc phrase bank.
- Settings: `UNIFIED_TURN_SHADOW_ENABLED` (default false).
- Hook in `execute_task_streaming` — async audit `unified_turn.shadow.completed`.
- Tests with mocked model response + knowledge-boundary classification.

Phases 2–4 remain gated on battery + latency + cutover per program prompt.

**Deploy note:** prod tip must advance past any pinned `GIT_SHA` for shadow audits to run live (`UNIFIED_TURN_SHADOW_ENABLED=true` alone is not enough if the image is stale).

### Phase 1 closed (2026-07-22)

See [`unified-turn-phase1.md`](unified-turn-phase1.md). Live PASS:
`unified_turn.shadow.completed` @ `2026-07-22T09:48:20.674876Z` on tip `acb44e3b…`
(conversation `51b39f39-f770-46f4-92ee-3584da9bda06`).
