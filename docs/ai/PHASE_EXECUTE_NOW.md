# CAN_THIS_ACTION_EXECUTE_NOW (post-audit next step 4)

**Status:** STRUCTURAL in merge tests (attach-time gate)  
**Date:** 2026-09-17  
**Does not expand F1. Does not change WRITE inference or G8.**

Named check `can_this_action_execute_now` / `CAN_THIS_ACTION_EXECUTE_NOW` runs **before model `tool_choice`**:

- `narrow_tools_for_turn` (ReAct + unified-turn keyword path)
- `embed_narrow_tools_for_turn` (unified-turn embedding path)
- `narrow_permitted_tools_for_capability` (governed assistant permitted-name list)

## What it uses

Cheap, already-in-memory signals:

- Turn `connected_integrations` snapshot
- Optional `unavailable_vendors` from org-context rows with `executionAvailable: false`
- Optional `availability_by_vendor` / catalog registered-action check when callers pass them

It does **not** call `evaluate_connector_availability(..., force_live=True)` per tool, and it is **not** HMAC preflight.

Platform / MCP / browser / capability / `web_search` names stay attachable so the model can still guide a connect path.

## Evidence bar

Local pytest on `backend/tests/services/test_action_execute_now.py` is structural only. Production PASS still needs a live turn after Railway deploy with a fresh trace (attached tools omit a mentioned-but-disconnected vendor).
