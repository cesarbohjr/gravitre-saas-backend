# Data storage and LLM transmission (canonical)

Last updated: 2026-07-07

This document is the internal source of truth for security reviews, sales engineering, and public FAQ alignment.

## Positioning statement (use in sales and trust materials)

> Gravitre does **not** require customers to migrate or centralize business data into a separate data platform. Information remains in the customer's existing systems and is accessed through authorized connectors. Gravitre stores only the operational data necessary to provide AI functionality, including conversation history, knowledge-base indexes, embeddings, workflow records, and audit information. For AI requests, only the specific retrieved passages and tool results required for the task are sent to the selected model provider — not full documents, embeddings, or bulk system exports.

Avoid claiming **"Gravitre doesn't store customer data."** That statement is inaccurate for the current architecture.

---

## What Gravitre stores (durable)

| Category | Where | Notes |
|----------|-------|-------|
| Conversation history | Supabase `conversations`, `conversation_messages` | User + assistant text, tool I/O in `tool_calls` jsonb |
| Knowledge base | `rag_documents`, `rag_chunks`, `rag_embeddings` | Chunk text + pgvector embeddings (1536-dim default) |
| Agent memory | `agent_memories` | Text + embeddings for per-agent recall |
| Workflow outputs | `workflow_steps.output_snapshot` (legacy), `runs` / `run_steps` metadata (contract) | Step-level JSON snapshots on legacy path |
| Connector credentials | Encrypted connector token storage | OAuth tokens / API keys per org |
| Audit | `audit_events`, `audit_logs` | Operator retention purge available (default 180d script) |
| Optional raw uploads | Supabase Storage `rag-uploads` | When `rag_store_raw_files=true` |

Org isolation: RLS on tenant tables. Data region: `organizations.data_region` (`us` \| `eu`).

---

## What is cached (ephemeral)

Redis when configured; in-process fallback per worker otherwise.

| Cache | TTL |
|-------|-----|
| RAG hybrid retrieval results | 5 minutes |
| Query embeddings | 7 days |
| Source summaries | 1 hour |
| Tier-0 instant answers | 1 hour |
| Org context snapshot | 60 seconds |
| Assistant duplicate-response | 30 seconds |

Caches may contain query text and retrieved chunk snippets. Treat Redis as sensitive ephemeral storage.

---

## What is sent to LLM providers

All completion traffic flows through `backend/app/services/model_router.py`.

### Sent

- System instructions (safety preamble + org/task context) — not PII-redacted
- User prompt — PII-redacted by default (`AI_PII_REDACTION_ENABLED=true`)
- Recent conversation turns (≈12) — redacted user/assistant content
- Retrieved **chunk text** (500–1200 chars per chunk depending on path; not full documents)
- Chunk/source metadata (title, score, labels)
- Org metadata snapshot (connector status, agent names, run counts — not bulk exports)
- Connector tool JSON results during ReAct (truncated ≈8000 chars per observation)
- Rolling conversation summary when context window fills

### Not sent

- Full source documents or connector bulk exports
- Embedding vectors
- Raw database dumps
- OAuth tokens / API keys
- Prompt bodies in `model_calls` billing table (tokens/cost only)

### Ingest vs inference

Documents are chunked (~1000 chars, 200 overlap) at ingest. Embeddings stay in Postgres. At inference, only matching chunk **text** is included in the model context.

---

## Admin controls

| Control | Mechanism |
|---------|-----------|
| Disable all AI | `DISABLE_AI` env / deployment killswitch |
| Per-org model allow/block | `organizations.settings.modelPolicy` — API `/api/settings/model-policy` |
| PII redaction | `AI_PII_REDACTION_ENABLED` (default on) |
| Rate / budget | `ai_rate_limit_per_min`, hard budget flags |
| Data residency | Org `data_region`; connector token region enforcement |

Known gap: model policy pre-check uses `provider="openai"` at enforcement time; verify failover paths in reviews.

---

## Retention gaps (disclose in diligence)

- No automated purge job for `conversation_messages` despite admin `memory_retention_days` setting (default 90 in dialogue settings API).
- Retention purge script targets audit tables (+ optional RAG retrieval logs), not chat.
- PII redaction is regex-based; ReAct tool observations are not redacted before provider calls.

---

## Related code

- `backend/app/services/model_router.py` — LLM chokepoint, redaction
- `backend/app/services/rag_service.py` — chunking, retrieval
- `backend/app/services/rag_cache_helpers.py` — cache TTLs
- `backend/app/routers/assistant.py` — conversation persistence
- `backend/app/services/model_policy_service.py` — org model policy
- `backend/scripts/retention_purge.py` — audit retention
