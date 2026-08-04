# Extension v4 enhance — handoff transcript + UX parity

Date: 2026-08-03

## Capability proof — PASS

Artifact: `docs/delivery/browser-extension-v4-handoff-transcript-live.json`  
Smoke: `scripts/live-extension-v4-handoff-transcript-smoke.py`

| Case | Result |
|------|--------|
| Overlay page-context Q | PASS — path `execute_task_streaming+page_context_answer` |
| Write handoff same thread | PASS — `conversationId` identical, `handoff_short_circuit` |
| Transcript both sides | PASS — 4 messages (user/assistant ×2) in `conversation_messages` |

Conversation: `cc618049-0d01-481a-95f7-7b87ad045ae9`  
Full app: https://gravitre.app/ai?c=cc618049-0d01-481a-95f7-7b87ad045ae9

## UX

1. **Side panel** — overlay does **not** duplicate `TaskSidePanel`. When `pending_task.params.steps` ≥ 3 (`EXTENSION_CHAT_SIDE_PANEL_STEP_THRESHOLD`, same as `SIDE_PANEL_STEP_THRESHOLD`), handoff reason `multi_step_progress` → continue in full chat where the panel lives.
2. **Matched preview** — BusinessOutcome cards remain on enrich/execute/workflow paths; overlay chat renders BO if present, otherwise plain answer (honest — chat path does not invent connector outcomes).
3. **Handoff URL** — write intents keep `&prompt=`; multi-step/approval handoffs use `/ai?c=` only so the persisted transcript hydrates without a duplicate auto-submit.

## Tests

`pytest tests/services/test_extension_bridge_service.py` — 9 passed (includes multi_step_progress handoff).
