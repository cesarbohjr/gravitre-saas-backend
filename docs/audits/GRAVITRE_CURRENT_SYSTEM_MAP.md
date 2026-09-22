# GRAVITRE — CURRENT SYSTEM MAP

**Audit date:** 2026-09-22  
**Git origin/main:** `5213d3dd`  
**Production backend:** `a7a0dd56` (`https://api.gravitre.app/health`)  
**Production frontend:** `a5f97faa` (Vercel `dpl_73ryW1MTFym3T7N35vnevDhvYCRD`)  
Evidence: **PRODUCTION VERIFIED** SHAs; **CODE INSPECTED** modules.

This map is implementation-grounded. Architecture docs are historical.

---

## High-level flow

```
User
 ├─ Web (Vercel Next)
 ├─ Desktop / helper window
 ├─ Mobile
 └─ Voice (mic or HTTP Talk)
      → Auth (session / JWT)
      → AI Workspace
           ├─ TEXT: POST /api/assistant/chat
           └─ VOICE: WS /api/voice/pipecat/ws  (JSON PCM16; WebRTC denied in prod)
                → AgentIntelligence.execute_task_streaming
                     ├─ Intent Gateway (shortcuts: connector_status, spoken hold)
                     ├─ CognitiveTurnKernel (Understand → Context → Plan → Capability →
                     │    Resource → Compile → Govern → Execute → Observe → Verify → Compose)
                     ├─ Unified LIVE tool loop  (prod flag true; embedding JIT)
                     └─ Classical ReAct          (fallthrough / non-LIVE)
                          → ActionSpec + HMAC/preflight
                          → PendingAction (WRITE)
                          → Connector adapters / F1
                          → Observations
                          → Response Composer (text vs spoken)
                          → SSE deltas or ElevenLabs PCM
```

Adjacent (not the chat SSE path):

```
Workflows → execution_engine_runtime.py → Temporal and/or asyncio
Agents / delegation → same tools if they call execute_task_streaming; else UNKNOWN
Intelligence UI → graph + outcomes display (does not execute)
Reports / predictive → mixed LLM + aggregation
Browser READ → httpx
Browser INTERACT → Playwright (flag default false)
```

---

## Stores (sources of truth)

| Class of truth | Canonical store | Alternate / duplicate | Active? |
|----------------|-----------------|----------------------|---------|
| Tenant/users | Supabase Postgres | — | PRODUCTION health database=healthy |
| Conversation / task_state | conversation_state (+ DEFAULT_TASK_STATE normalize) | durable_checkpoint / durable_session | LIVE proven after 3.0-D persist fix |
| Connector credentials | org connectors + OAuth | pending_auth | LIVE isolated org |
| Action catalog | ActionSpec registry | capability ontology maps | CODE ~731 unique / ~755 registered |
| Documents / RAG | knowledge_sources / chunks + pgvector `rag_embeddings` | Pinecone Sources driver | pgvector primary |
| Entities | org_business_entities (HMAC mentions) | fuzzy UI search | STA-312 exact match |
| Outcomes | intelligence_outcome_events | UI “learning” copy | persist yes; consume weak |
| Analytics | ClickHouse | Postgres rollups | configured |
| Cache | Redis | in-process | healthy |
| Workflow durable | Temporal | cron/asyncio | configured |
| Audit | audit_events | — | CODE + prior live PASS rows |

---

## Layer table

| Layer | Canonical | Alternate | Bypass / parallel |
|-------|-----------|-----------|-------------------|
| Ingress | chat + pipecat WS | HTTP Talk voice | WebRTC blocked |
| Intent | Intent Gateway | model-only ReAct | connector_status shortcut |
| Context | ContextCompiler | ad-hoc prompt builders | UNKNOWN residual |
| Memory | conversation_state + durable_checkpoint | RAG, entities, outcomes | three memories |
| Knowledge | Knowledge Fabric pgvector | web research (prod enabled) | internet vs tenant |
| Intelligence/ML | embeddings + heuristics + LLM | “trained” UI language | see learning audit |
| Reasoning/planning | Kernel + LIVE or ReAct | workflow planner | dual tool brains |
| Capability / resource | ontology + resource resolver | connector-specific patches | vendor ifs in runtime |
| Governance | HMAC, write_allowed, PendingAction | workflow engine must not skip | watch |
| Execution | F1 adapters | generic HTTP | browser interact off |
| Observation | Observation objects | workflow logs | not one schema |
| Verification | QA hooks prod true | Composer restatement | |
| Learning | outcome events | none closed-loop | |
| Response | Response Composer | raw model text | workflows skip Composer |
| Output | SSE / PCM / UI | notifications | |

---

## Runtime flags (prod `/health` vs code default)

| Flag | Prod | Code default |
|------|------|----------------|
| unified_turn_live_enabled | true | false |
| unified_turn_shadow_enabled | true | (settings) |
| embedding tool retrieval | true | |
| min catalog tools | 40 | |
| task model tier | low | |
| internet_research_enabled | true | |
| browser_agent_interact | not on health | false |
| WebRTC media | — | production_allows_webrtc_media() false |

---

## Dependency sketch

Users → Vercel → FastAPI Railway → Postgres/Redis → OpenAI (preferred) / Anthropic / Gemini → connectors (Apollo, HubSpot, Google, …) → Deepgram/ElevenLabs → ClickHouse/Temporal.

**CODE EXISTS vs ACTIVE vs LIVE vs SHADOWED**

- LIVE: execute_task_streaming, HMAC, Isolated-org pending_auth, LIVE flag, PCM STT, HTTP Talk SLO, durable_checkpoint after D.  
- SHADOWED: unified_turn_shadow still true alongside LIVE.  
- UNUSED / WEAK: Pinecone as primary RAG; Playwright interact; native WebRTC.  
- DUPLICATED: LIVE vs ReAct; HTTP Talk vs Pipecat; pgvector vs Pinecone driver.
