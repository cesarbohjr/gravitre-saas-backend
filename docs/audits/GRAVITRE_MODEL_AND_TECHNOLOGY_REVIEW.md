# GRAVITRE — MODEL AND TECHNOLOGY REVIEW

**Audit only.** 2026 greenfield comparison vs current wiring.  
Evidence: **CODE INSPECTED** `MODEL_TIERS` / adapters; **PRODUCTION VERIFIED** `unified_turn_task_model_tier=low`. Tokens, $ / task, cache hit: **UNKNOWN**.

---

## Current inventory (wired)

Preferred provider: **openai**. Failover: anthropic, gemini. groq/together/azure: unused.

| Role | Current | Notes |
|------|---------|--------|
| Fast / prod tools (low) | gpt-5.4-mini / claude-haiku-4-5 / gemini-2.5-flash | **This is what prod health says it uses** |
| Complex (medium_high) | gpt-5.5 / claude-sonnet-4-6 / gemini-2.5-pro | Not the prod task tier |
| Vision | **gpt-4o** / claude-3-5-sonnet-20241022 / gemini-2.5-pro | Dated vs rest of stack |
| Voice conversational | gpt-5.4-nano | Speed-first |
| Web research | gemini-2.5-flash | Prod internet_research true |
| Embed | text-embedding-3-small | pgvector |
| Tool embed | all-MiniLM-L6-v2 local | JIT |
| Rerank | ms-marco MiniLM L6 | |
| Moderation | omni-moderation-latest | |
| STT HTTP | Deepgram nova-2 | |
| STT Pipecat | flux-general-en | LIVE PCM |
| TTS | eleven_flash_v2_5 | |
| OpenAI transcribe | gpt-4o-mini-transcribe | |
| Fine-tune base | gpt-4.1-mini | **UNKNOWN** if live trained models serve prod |

Call sites: `model_router.py` stream; unified_turn OpenAI tools streaming; non-OpenAI `provider_tool_router` **non-stream**; ReAct mixed; Composer extra call; embeddings; guardrails; voice bridge **does not** use Pipecat’s OpenAI LLM.

---

## Where LLMs are used vs should be deterministic

| Job | Today | Recommendation |
|-----|-------|----------------|
| Connector connected? | Gateway shortcut | **PRESERVE** deterministic |
| Spoken yes/wait | hold_commit | **PRESERVE** |
| HMAC / preflight | deterministic | **PRESERVE** |
| Pack-common list create | retrieve_plan_gate | **PRESERVE** |
| Tool selection | LIVE/ReAct LLM | JIT already; keep model |
| Intent class | mixed | Do not add a **second** classifier LLM in front of LIVE |
| Composer | extra LLM | **OPTIMIZE** — skip when payload already spoken-complete |
| Entity fuzzy join | forbidden STA-312 | **PRESERVE** no LLM join |
| Verification critic | QA hooks prod true | Keep for WRITE/high risk only |

---

## If selecting families in 2026 (categories, not a bake-off winner)

Do **not** replace because newer. Evaluate:

| Category | Current fit | 2026 eval worth it? |
|----------|-------------|---------------------|
| Fast conversational | mini/nano/haiku/flash | Keep; measure TTFT |
| Complex reasoning | gpt-5.5 / sonnet 4.6 / 2.5 pro **unused as prod task tier** | **Yes** — route hard business questions up |
| Tool use | OpenAI streaming tools vs non-OpenAI non-stream | Streaming parity for failover |
| Coding | not first-class product | no dedicated coder unless computer-use |
| Long-context | UNKNOWN window usage | measure before switching embed/chat |
| Structured extract | JSON/tools | keep |
| Classification | gateway + model | min routing |
| Voice/realtime | cascaded Flux+EL | hybrid native realtime **evaluate** |
| Vision | gpt-4o / 3.5 sonnet | **REPLACE candidate** |
| Computer use | absent product | new **strategy**, new model family later |
| Embedding | t-e-3-small | adequate unless recall fails golden set |
| Rerank | MiniLM | eval vs stronger rerank if RAG is the miss |

---

## Routing architecture (minimum)

Prod already has **tiers**. The bug is **everything live uses low**.

Minimum routing:

1. Deterministic shortcuts (no model).  
2. Voice hold / acknowledgements → nano.  
3. Default assistant tools → current low (latency).  
4. Ambiguous multi-source / WRITE / “how is the business” → medium_high **once**.  
5. No extra classification LLM whose only job is to pick the tier if heuristics (tool count, WRITE, multi-connector, token estimate) suffice.

Extra routing calls that duplicate Intent Gateway: **avoid**.

---

## Prompt / cache (this audit)

Payload dumps: **UNKNOWN**.  
JIT visible tools p95=20: **LIVE** — schema bloat of 700 tools is **not** the current failure mode.  
Composer + history replay: likely churn (**CODE INSPECTED**, unmeasured).  
Cache hit rate: **UNKNOWN**.

---

## Broader 2026 stack “would we choose this?”

| Layer | Today | Change? |
|-------|-------|---------|
| Frontend | Next on Vercel | PRESERVE |
| API | FastAPI Railway | PRESERVE |
| DB | Postgres/Supabase | PRESERVE |
| Vector | pgvector | PRESERVE (not Pinecone primary) |
| Cache | Redis | PRESERVE |
| Workflow | Temporal + asyncio | PRESERVE both until Temporal owns crons |
| Analytics | ClickHouse | PRESERVE; **consume** in ops |
| Voice | Pipecat/Deepgram/EL | PRESERVE + eval hybrid |
| Browser | httpx + Playwright flag | EXTEND strategy later |
| Observability | custom stages + health | EXTEND unified trace contract |

**No technology churn for fashion.**
