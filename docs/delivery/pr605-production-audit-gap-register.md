# PR #605 — Production-baseline ecosystem audit and gap register
Date: 2026-11-04. Status: **IN PROGRESS**. Evidence-based inventory; not a completed full audit or certification.
Production code baseline: `557be844f191767ea51c9f1d1d4958e5b046ca53` (PR #601 merge).
Audit branch: `feat/gravitre-unified-ecosystem-modernization`.

## Production identity evidence (verified through connected hosting accounts)
- Railway project `spirited-communication` (`6017a555-f639-4b28-b538-031b5119e1e3`), environment `production`, backend service `gravitre-saas-backend` (`20c41db0-3e3d-400e-95d5-eef57ba2bc0c`): latest deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb`, status SUCCESS, branch main, commit `557be844f191767ea51c9f1d1d4958e5b046ca53`.
- Railway Redis is a separate service (`f59baa77-47e3-460f-8437-3b79273317ae`). A separate Railway project `Gravitre front-end` contains `gravitre-saas-interface`; determine whether it serves production or is historical/parallel before retirement.
- Vercel project `gravitre-saas-backend` (`prj_ZKQZcnavQ8UnQTWH85125nBgTVfO`): latest listed production deployment `dpl_4E97DHDQJSRFPuRmARbSpHZoVVwC` READY, GitHub branch main, commit `557be844f191767ea51c9f1d1d4958e5b046ca53`.
- These are **hosting deployment records**, not proof that every route, feature flag, service integration, or user request works. Domain alias, HTTP health and live customer paths still need verification.
- GitHub `main` tree SHA `557be844f191767ea51c9f1d1d4958e5b046ca53`; recursive tree returned 13,299 entries. Scope is substantial; sampling is not a complete dependency audit.

## Findings grounded in code at the exact production commit
| ID | Priority | Evidence | Observed fact / risk | Next verification |
|---|---|---|---|---|
| ECO-001 | P0 | `backend/app/operators/agent_intelligence.py` (~324KB); `backend/app/services/intelligence_router.py` (~41KB); `backend/app/orchestration_registry.py` | Several orchestration surfaces exist; registry describes IntelligenceRouter as 10-stage wrapper around AgentIntelligence and additional facades. **Competing authority remains a hypothesis**, not established for every route. | Build actual ingress-to-runtime call graph and per-route decision ownership; prove runtime flags. |
| ECO-002 | P0 | `intelligence_router.py` `route` | Sequential awaits for policy/settings, understanding, classification and cluster enrichment are present. Some downstream work uses `asyncio.gather`. | Capture per-stage timings, provider calls and dependencies; parallelize only independent stages. |
| ECO-003 | P0 | `context_assembler.py` | Retrieval, company context and conditional research are awaited in sequence. | Profile relevant routes and safe concurrency/caching with tenant isolation. |
| ECO-004 | P0 | `backend/app/services/pipecat_voice/transcript_relay.py` | Final transcript relay is necessary because aggregator consumes transcript frames; backchannel/echo classification influences whether browser treats final as new turn. This is a documented historical defect and repair surface. | Trace STT final IDs, relay, browser state, turn strategy, playback and persisted messages; test duplicate `check check` / `update update`, interruptions and backchannels. |
| ECO-005 | P0 | `backend/app/services/chat_tool_bridge.py` | Dynamic chat tools are generated from connector execution matrix and registered actions; presence in catalog is not proof of tenant connection or actual execution. | End-to-end simple connected reads, missing scope, disconnected tools, approvals and outcome verification. |
| ECO-006 | P1 | `docs/audits/GRAVITRE_CURRENT_SYSTEM_MAP.md` (dated 2026-09-22) | Historical map reports LIVE vs ReAct, multiple memory and voice paths, weak feedback consumption. **Historical only**; not sufficient to delete components in November production. | Revalidate each entry at 557be844, mark ACTIVE / INACTIVE / UNKNOWN and actual callers. |
| ECO-007 | P1 | `.github/workflows/` inventory in main | Many specialized voice, intelligence, production and live-provider gates; risk of overlapping, skipped or contradictory certifications. | Enumerate triggers, required checks, paid-provider dependencies, coverage and obsolete jobs. |
| ECO-008 | P1 | Hosting inventories | Railway frontend project and Vercel frontend deployment both exist. This does not establish that they are redundant. | Map DNS/domain routing, traffic, build source, deployment SHA, service dependencies and costs. |
| ECO-009 | P0 | User production feedback | Repetitive low-initiative responses, weak task execution, STT duplication, stuttering and choppy voice are acceptance failures. | Correlate a real anonymized trace across STT, model, tools, TTS, transport and client; reproduce with synthetic regression. |
| ECO-010 | P1 | Architecture requirements | Memory, outcome, approvals, plays, workflow and agent components need a canonical end-to-end outcome contract. | Verify every path uses the same write fence, durable state, observation and final result semantics. |

## Retirement policy and current decisions
- **No deletion approved yet.** Every candidate must have verified production usage, exact consumers, migration target, equivalent capability, security invariant, regression test and rollback plan.
- Keep safe retry, idempotency, recovery, and equivalent-contract provider resilience. Remove silent weaker behavioral fallback and duplicate decision authority after migration.
- Distinguish provider configured, tool registered, tenant connected, action authorized, action executed and outcome verified.
- One shared runtime with conversational/direct-task/goal-driven workload modes; no forced sequential traversal for trivial requests.

## Required full-audit coverage before architecture freeze
1. Frontend surfaces and actual production DNS/route/voice clients; browser streaming and state.
2. Backend HTTP/WS/SSE entry points, middleware, settings, feature flags, model policy, prompt and context builders.
3. Voice STT endpointing, interim/final transcript IDs, Pipecat transport, TTS synthesis/chunking, PCM playback, cancellation and echo.
4. Agents, plays, packages, workflows, Temporal/asyncio, tool registries, connector OAuth/Nango/native paths and execution authorization.
5. Persistence (Supabase/Postgres), Redis, analytics, RAG/knowledge, memory, checkpoints, tenant boundaries and retention.
6. Model/Deepgram/ElevenLabs API usage, credits, rate limits, token/voice-minute costs and provider fallback semantics.
7. Hosting config, secrets **names only** (never values), deployment routes, health, operational telemetry and error rates.
8. Tests/CI, exact-head workflow outcomes, security and governed-action regression coverage, legacy/shadow flag owners.
9. Performance traces, customer journeys, task outcome accuracy, latency and subjective voice acceptance.

## Deliverables / stop conditions
- Route/dependency graph with owner, source, production status, consumers and proposed action for **every in-scope subsystem**.
- Gap register with severity, impact, root-cause evidence, target repair, dependencies, migration test and risk.
- KEEP / CONSOLIDATE / UPGRADE / RETIRE register with proof; no speculative deletion.
- Revised implementation order and measurable acceptance gates committed to PR #605.
- No claim of complete audit, parity, repaired defects or release certification until supported by evidence.
