# Phase F — Conversational seamlessness

**Status:** F1 implemented locally (PARTIAL until prod Stop evidence). F2 in progress. E6 remains `EXTERNAL_BLOCKED` until smoke-org GA4 OAuth is completed in production. There is no cognitive E7.

This phase is **not** Intelligence G8 / I*. It is the chat runtime: stop, honesty of first token, typed parts, resumable streams, latency, and interrupt recovery — the gap between “a governed operator” and ChatGPT / Claude as a daily conversation.

## Why this exists

Phase E closed plan-first dispatch (backend SoT). Live GA4 verification is still blocked on human Google reconnect. The next user-visible deficit is **conversation control**, not another connector patch.

Research (2026 product bar, not marketing claims):

| Pattern | What ChatGPT / Claude do | Gravitre today |
|---|---|---|
| Stop | Stop aborts **server work**, not only the browser reader | `useChat().stop()` aborts the fetch; FastAPI keeps planning/tools until the generator finishes |
| First token | Status / tool intent before claims | Long silent planning; copy can read as “done” before tools |
| Typed parts | Text vs tool vs reasoning stay distinct | Mixed SSE; post-tool prose can leak before the gate |
| Resume | Disconnect ≠ lose the turn (replay / Last-Event-ID) | Dropped SSE = dead turn |
| TTFT | Prompt cache + early status | Full context rebuild every turn |
| Interrupt | Stop, then “continue” from partial | No cooperative cancel; no resume contract |

## Constraints

- Do not invent customer-facing prices, badges, Enable toggles, or “live ChatGPT-level” claims.
- Dual paths: `/ai` and `/agents/[id]/chat` both must honor stop.
- Evidence-linked PASS: F1 is **PARTIAL** until a prod stream shows `assistant.chat.stopped` (or equivalent guardrail/audit) after Stop, with tools not continuing after the flag.
- Cooperative cancel: in-flight connector HTTP may finish the current call; the loop must not start the **next** model/tool step.

## Phases

### F1 — Cooperative stop (this increment)

Redis `SETEX chat:stop:{org_id}:{conversation_id}` (TTL 120s) plus in-process fallback. `POST /api/assistant/chat/stop` (proxied as `POST /api/chat/stop`). Stream loop checks the flag and `Request.is_disconnected()`. UI Stop POSTs then calls `stop()`.

**Done when:** Stop during a streaming turn leaves a finished (or empty “Stopped.”) bubble, server logs/guardrail `assistant.chat.stopped`, and no further tool invoke for that conversation until the next user message.

### F2 — First-token / tool-intent honesty (this increment)

Emit user-status / progress **before** connector gather and before any claim that work finished. Never paint standalone “Done.” until `execution_verified` is true on the envelope. Align waiting label with actual stage (plan / tool / compose). Progress acks use composer kind `progress`, not `success`.

**Done when:** A live `/ai` stream shows `userStatus.label` = “Understanding your request” (or mapped equivalent) before the first text-delta, and a write that is still awaiting confirm never streams a bare “Done.”

### F3 — Typed parts and post-tool gating

Keep tool chips out of the prose bubble. After tools, compose only from the user envelope (existing `response_composer`) — no raw model dump of tool JSON.

### F4 — Resumable streams

Optional Last-Event-ID / conversation replay so a proxy blip does not discard a completed backend turn. Do not start until F1 is proven; resume of **in-flight** tools is a later slice.

### F5 — TTFT and cache

Honest first-token timer already exists (`ChatPerfTimer`). Next: reuse conversation prefix / provider prompt cache where the vendor supports it; do not cache confirmations (`yes`/`no`) across conversations (existing response-cache rule).

### F6 — Interrupt recovery

After Stop, a “continue” user turn must see persisted partial assistant text + ledger, not a blank slate. Depends on F1 persist-on-cancel.

## Out of scope

- ReAct / voice / workflow rewrites except consuming the cancel flag.
- GA4 architecture patches (E6 OAuth is a human reconnect).
- Intelligence hub G8 UI.

## Evidence

Local pytest is the gate to merge F1. Production PASS requires a live `/ai` Stop during a streaming turn after deploy.
