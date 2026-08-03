# Browser extension v4 — lightweight chat from the overlay

Date: 2026-08-03  
Baseline: v3 tip `ab5ce40b`

## Model

Overlay asks a quick, page-contextual question through the **same** `execute_task_streaming` / unified-turn path as main chat. Page facts are injected as DATA (system prompt + compact fact sheet). Write / longer intents set `needsHandoff` and open `/ai?c={conversationId}` so the thread continues in full Gravitree chat. No parallel reasoner.

## API

| Method | Path | Role |
|--------|------|------|
| POST | `/api/extension/chat` | Quick Q&A → answer + conversationId + handoff URL |

## Client

- Manifest `0.4.0`
- Background message `CHAT`
- Overlay input “Ask about this page” + Continue in Gravitree

## Live proof — local PASS

- Quick page-context Q: conversation `a5d8df4f-c32b-4d32-90e1-3995d6bd7adf`
  - Answer: “Casey Operator — Head of Revenue Ops at Gravitree Smoke Co.”
  - Path: `execute_task_streaming+page_context_answer` (same unified-turn entrypoint; LIVE often returns an unusable connector plan for fact questions, so overlay prefers page-context facts over that plan)
- Handoff: HubSpot list create intent → `needsHandoff=true`, `/ai?c=…&prompt=…`, path `handoff_short_circuit`

Artifacts: `browser-extension-v4-live.json`, tip verify after deploy.
