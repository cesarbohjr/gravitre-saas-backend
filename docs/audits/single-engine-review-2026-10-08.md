# Single-engine implementation review — 2026-10-08

Status: PARTIAL IMPLEMENTATION VALIDATED; END-TO-END ACCEPTANCE NOT VERIFIED.
Reviewed main 10ce513e763f04b52a5884487a97252f715d4062. Railway's last successful backend deployment is b398d01e0ba72e07c28cf6239c05d03ab47a8c0b; the subsequent roster-only deployment was SKIPPED. The fixes accompanying this report are not deployed.

## Actual paths inspected

| Surface | Actual code path | Evidence scope |
| --- | --- | --- |
| Text | routers.assistant.assistant_chat → shared_turn_preparation guardrails → _build_stream → AgentIntelligence.execute_task_streaming → CognitiveTurnKernel.run_pre_act → canonical compiled-read / ReAct execution → response composition and persistence | Code inspection and incident production records |
| Pipecat voice | pipecat_voice.cognitive_llm.GravitreCognitiveLLMService → guard_spoken_turn + AgentIntelligence.execute_task_streaming(spoken_mode=True) → shared kernel / runtime → spoken composition → TTS | Code inspection; live audio not tested here |
| Agent job | operators.agent_jobs → AgentIntelligence.execute_task → CognitiveTurnKernel.run_pre_act | Code inspection; non-streaming wrapper is distinct |
| Play | routers.plays inserts play_run and iterates bindings → routers.workflows.execute_workflow → execute_workflow_steps | Code inspection |
| Workflow | routers.workflows.execute_workflow or _execute_workflow_with_context → execute_workflow_steps | Code inspection; two ingress wrappers remain |
| Scheduled workflow | schedule_scheduler → dispatch_due_workflow_schedules → _execute_scheduled_workflow → _execute_workflow_with_context → execute_workflow_steps | Code inspection |

These paths reuse reasoning or governed execution primitives. That does not prove every path enters the same reasoning stages. A precompiled workflow legitimately executes a stored plan; its governance and outcome semantics still need live parity checks.

## Fork inventory

| Location | Purpose | Assessment | Remediation/status |
| --- | --- | --- | --- |
| AgentIntelligence.execute_task / execute_task_streaming | Job result vs interactive streaming | Both call the kernel; large separate wrappers remain | Full divergence inventory NOT VERIFIED |
| assistant_chat vs guard_spoken_turn | HTTP refusal vs spoken refusal | Shared guardrail helpers are appropriate; preparation ordering differs | Text performs synchronous prompt/summary reads before StreamingResponse; unresolved |
| Spoken tier context and sentence streaming | Audio latency/presentation | Intentional only if semantic requirements survive pruning | Owner-tenant equivalence NOT VERIFIED |
| execute_workflow / _execute_workflow_with_context | HTTP vs internal caller | Legitimate wrappers around execute_workflow_steps | Live approval/outcome equivalence NOT VERIFIED |
| intent_gateway response cache | Shortcut answers | Incorrect for current business reads; production resend reused an incomplete answer | Disabled for named connector/business-record read questions |
| cognitive_execution_replanner | GA/GSC composition | Missing capability incorrectly selected analytics | Removed empty-capability match |
| canonical_cognitive_resolution | Compiled read selection | Old analytics state could win over an explicit/continued listing read | Resolve nearest read continuation; listing before analytics; preserve pending approvals |

## Incident proof and corrections

Saved prompt: “How many companies do I have in HubSpot?” The first assistant message contains a knowledge-base/web search and hubspot_companies_search(limit=1), with paging.next and no total. It offers a full count instead of obtaining it. The identical resend stores the same answer with no tool calls. “Ok do that” stores an ungrounded-read fallback and a compiled analytics.traffic_overview task with GA/GSC observations, not a company count.

The first request's logged planning was 20,356 ms. Its stream timer was 21,858 ms; pre-stream HTTP timing was separately 3,897 ms. At refresh, conversation load returned zero messages and replay returned 404 before completion persistence. Request-id correlation supports this sequence; it does not prove the browser's timeout mechanism.

The 23:57:27 UTC ReadError was in workflows.list_approvals_alias, not the chat stack. Similar failures affected agent worker ticks. Connection/resource contention remains a hypothesis; no transport fix is claimed.

Reused primitives: shared_turn_preparation, CognitiveTurnKernel, listing_f2_read_turn, sealed F1 read invocation, provider search total, execution plans/observations, durable work artifacts, evidence grounding, io_pool, shared workflow runtime. No new planner or execution engine was created.

Removed behavior: empty capability → analytics; cached live-read refusal; explicit company count → generic model tool choice; recent read continuation losing to an unrelated analytics plan. These are corrected dispatch decisions, not deletion of whole runtime modules.

## Acceptance still open

Durable acceptance and in-flight recovery, safe resend across active turns, full duplicate-engine inventory, live owner-tenant execution and external outcome verification, all-surface governance parity, provider-failure recovery, hardware voice interruption/dead-air, and comparative human evaluation remain NOT VERIFIED. Current evidence cannot answer the final product-standard question with a demonstrable yes.
