# Gravitre Unified Ecosystem Modernization & Parity — Governing Engineering Plan
Status: Proposed, not implemented or certified. Date: 2026-11-04.
Baseline: main after PR #601. This is a single coordinated engineering PR with staged, testable commits.

## Mission and product acceptance
Build one coherent, low-latency, enterprise-grade AI platform across voice, text, agents, plays, workflows, connectors, data, security and infrastructure. Human production feedback confirms defects in transcription duplication, choppy audio, repetitive and shallow dialogue, context use, tool initiative and single-task execution. Treat these as product acceptance failures; root causes require code/telemetry evidence. The customer supplies final experiential acceptance only after engineering certification.

## Non-negotiable architectural principles
1. One authoritative owner for each decision, state transition and execution contract.
2. Workload-adaptive execution through ONE runtime: conversational answer, direct task, or goal-driven autonomous plan; these are modes, not competing architectures.
3. Every component must have a justified role, explicit dependencies, typed/versioned interface, traceability, and measurable value.
4. Remove obsolete compatibility adapters, duplicate routing and shadow engines after consumer migration and verified coverage.
5. No silent downgrade to a weaker reasoning/tool path, no fabricated action completion, no governance bypass. Fail clearly or recover only under an equivalent contract.
6. Retain essential operational resilience: bounded retries, idempotency, durable checkpoints, authorized equivalent-provider recovery and infrastructure redundancy. Do not confuse resilience with behavioral fallback.
7. Prefer engineering and current infrastructure over new paid services. Avoid sequential processing that is not a real dependency.
8. Preserve tenant isolation, approvals, consent, audit, write fences and the semantics of read vs write actions.

## Target logical flow
Web / mobile / desktop / voice / API
→ Canonical conversation and intent runtime (turn state, intent, context, memory, sentiment, preferences)
→ Unified decision/orchestration kernel (reasoning, adaptive model selection, task decomposition, capability matching)
→ Governed execution fabric (agents, plays, workflows, connectors, approvals, observation, verification)
→ Unified response and delivery (grounded outcome, natural text, continuous duplex speech).
Cross-cutting foundation: identity, tenant permissions, durable state, storage, eventing, telemetry, reliability, cost governance.
This is a logical graph, NOT a mandate for every simple query to execute every stage.

## Architecture consolidation register (candidate decisions, verify before deletion)
| Existing patterns | Target decision and migration requirement |
|---|---|
| Unified LIVE vs classical ReAct | One canonical tool loop; retire classic routing only after equivalent capability, governance and recovery tests |
| IntelligenceRouter / AgentIntelligence / additional facades | One decision authority; specialist components remain callable modules, not competing orchestrators |
| ContextCompiler / ContextAssembler / ad hoc prompt builders | One context assembly contract; modular knowledge and memory sources with bounded budgets |
| conversation_state / durable_checkpoint / durable_session | One authoritative turn-state model; durable projections/checkpoints for recovery |
| Pipecat duplex / HTTP Talk / older voice paths | One production duplex voice runtime; migrate supported clients before retiring entry points |
| Connector status, ontology, registry, dynamic tool bridge | One tenant-aware capability catalog, executable availability and permission check |
| Agent and workflow execution | Common governed action/observation/outcome contract; distinct engines allowed only for justified workload semantics |
| Raw model output / response composers | One response envelope that distinguishes answer, suggestion, approval request, progress and verified result |
| Multiple model selectors | One model policy across providers and surfaces, with capability, quality, latency and cost constraints |
| Outcome hooks / analytics / feedback | One trace/outcome schema with actual consumers and privacy-safe feedback |
| Shadow/experiment flags and obsolete compatibility | Isolate from production; retire after consumer and rollout inventory |
These are proposed decisions, not findings that each named component is broken.

## Workstreams
A. **Current-state dependency and production-route graph.** Inventory ingress routes, active feature flags, model/provider choices, storage, auth, frontend/backend, voice transport, workflow engines, tool bridges, hidden fallbacks, tests and costs. Label each KEEP / CONSOLIDATE / UPGRADE / RETIRE. Identify exact callers and migration order.
B. **Canonical conversation and intelligence.** Unified turn IDs, interim/final transcript semantics, context relevance, memory, sentiment, user preferences, model selection and coherent response behavior. Remove repeated or contradictory prompt/inference stages. Prove that computed intelligence affects decisions.
C. **Governed autonomous execution.** Reliable single-task recognition and authorized read execution first; then multi-step dependencies, agent/play/workflow suggestions, approval/revocation, durable execution and verifiable completion. Never claim execution when only a plan or proposal exists.
D. **Duplex voice correctness.** Deepgram STT event sequencing, echo/backchannel and endpointing, transcript deduplication, Pipecat transport, ElevenLabs TTS chunk timing, PCM continuity, buffering, cancellation/barge-in and reconnection. Single authoritative session state across backend and client; correlate speech, model and playback events.
E. **Platform/data/infrastructure.** Supabase/Postgres, Redis, Temporal, analytics, event lifecycle, caches, source-of-truth reconciliation, Vercel/Railway deployment and operational health. Remove unused infrastructure only after usage/dependency evidence.
F. **Performance, economics, and quality.** Instrument per-stage TTFT, time-to-first-audio, end-to-end task completion, transcription duplication, TTS starvation, tool success, token spend, voice minutes and costs. Parallelize independent stages, cache safely, choose model based on task, enforce budgets without silent quality downgrade.

## Controlled retirement policy
Obsolete: delete after dependency audit. Duplicate: converge to one authority. Compatibility: migrate clients, then remove. Shadow/experimental: exclude from production path. Silent behavioral fallback: prohibit. Essential resilience: keep with same policy and state invariants, bounded retries, idempotency and clear failure reporting. Provider substitution only if capability, permissions and quality contract are equivalent.

## Workload modes under ONE runtime
- Conversational: natural, grounded, context-aware reply with no unnecessary orchestration.
- Direct task: resolve intent → discover capability → authorize → execute → observe → verify → report.
- Goal-driven: plan dependencies → suggest agents/plays/workflows → obtain necessary approvals → execute/monitor/recover → verify outcomes and communicate progress.
Modes may transition during one conversation without losing state.

## Execution sequence / gates
1. Freeze baseline and capture actual production routes, flags, traces, costs and known failing user journeys.
2. Write typed canonical contracts, migration dependency graph, retirement register and regression tests BEFORE deleting old code.
3. Migrate critical-path single tasks and voice turn state, including security/approval invariants.
4. Consolidate orchestration, context, capability registry, model policy and response envelope; migrate all supported surfaces.
5. Reconcile agents, plays, workflows, infrastructure and analytics; remove verified redundant paths and flags.
6. Optimize latency and voice continuity; measure costs and accuracy; prove no hidden degradation.
7. Exact-head CI: unit, integration, governed-action write fences, tenant isolation, synthetic audio, interrupted turns, tool outcome verification, crash/restart, latency and full customer journeys. Record actual pass/fail/skipped results, SHA and links.
8. Meet required GitHub reviews/protections; merge only a green certified head; deploy and verify frontend/backend SHA and health.
9. Live production provider/audio acceptance (including Deepgram, ElevenLabs, selected LLMs, real recordings, 20-minute dialogue, authorized single/multi-goal journeys) AFTER deployment. Customer makes final subjective acceptance decision. No pre-merge paid/live tests unless separately approved.

## Acceptance matrix
- Simple authorized tasks reliably route, execute, verify and report without avoidable clarification.
- Multi-step tasks respect dependencies, approvals, state, retries and cancellation.
- Complex business goals offer relevant capabilities and execute approved work, not just suggest it.
- Context and preferences persist correctly across turns and supported surfaces.
- Voice has no reproducible phantom/duplicate user turns, audio starvation, cross-turn bleed or broken barge-in in defined scenarios.
- Dialogue is relevant, proactive when appropriate, concise, non-repetitive and naturally expressive.
- End-to-end latency and cost are measured against agreed budgets, with quality retained.
- No unauthorized writes, fabricated completions, tenant leakage, or hidden weak fallback.
- Production deployments verified; final human acceptance required.

## PR implementation governance
One coordinated PR, multiple reviewable commits, evidence-backed decisions and explicit retirement ledger. Do not add new vendors or infrastructure without documented existing-stack limitation, cost analysis and measured expected benefit. No merge/deploy until implementation and gates pass. A planning-only commit must never be described as a completed repair.
