"""Scratch probe: confirm the approval-binding net is load-bearing.

Runs the originally reported divergence (HubSpot approved, Apollo executed)
twice through the real execute_plan:

  1. net intact   -> vendor invoke must NOT happen
  2. net disabled -> vendor invoke DOES happen

Step 2 is what proves the passing tests are not vacuous. Patches the net at
runtime only; production source is never modified.

Run: python scripts/scratch_verify_approval_net_load_bearing.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.chat_connector_execution_service import (  # noqa: E402
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.tool_registry import get_tool_registry  # noqa: E402

PAIRS = [
    ("hubspot_contacts_create", "hubspot.contacts.create", "hubspot",
     "apollo_lists_create", "apollo.lists.create", "apollo"),
    ("slack_post_message", "slack.post_message", "slack",
     "gmail_messages_send", "gmail.messages.send", "gmail"),
    ("notion_pages_create", "notion.pages.create", "notion",
     "asana_tasks_create", "asana.tasks.create", "asana"),
]


def _plan(tool: str, action: str, integration: str, args: dict) -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name=tool,
        invoke_action=action,
        integration=integration,
        kind="write",
        label=f"{integration} write",
        args=args,
        requires_approval=True,
    )


async def _run_once(pair, *, disable_net: bool):
    a_tool, a_action, a_int, x_tool, x_action, x_int = pair
    service = ChatConnectorExecutionService()
    registry = get_tool_registry()
    service._registry = registry
    service._finalize_connector_outcome = MagicMock()
    service._summarize_result = MagicMock(return_value="done")
    service._external_url = MagicMock(return_value=None)
    service._state = MagicMock()
    service._state.get_task_state = AsyncMock(return_value={})
    service._state.update_task_state = AsyncMock(return_value={})

    approved = ChatConnectorExecutionService.plan_to_dict(
        _plan(a_tool, a_action, a_int, {"properties": {"firstname": "Ada"}})
    )
    executed = _plan(x_tool, x_action, x_int, {"name": "divergence-probe"})

    invoke = AsyncMock(return_value={"success": True, "action": x_action, "result": {"id": "1"}})

    stack = [patch.object(registry, "execute_invoke_action", invoke)]
    if disable_net:
        stack.append(
            patch(
                "app.services.approval_action_binding.assert_plan_matches_binding",
                lambda *a, **k: None,
            )
        )

    for ctx in stack:
        ctx.__enter__()
    try:
        result = await service.execute_plan(
            org_id="org-probe",
            user_id="user-probe",
            conversation_id="conv-probe",
            plan=executed,
            client=MagicMock(),
            classification={},
            approved_params=approved,
        )
    finally:
        for ctx in reversed(stack):
            ctx.__exit__(None, None, None)

    return result, invoke.await_count


async def main() -> int:
    failures = 0
    for pair in PAIRS:
        label = f"{pair[1]} approved -> {pair[4]} executed"

        result, calls = await _run_once(pair, disable_net=False)
        intact_ok = calls == 0 and result.success is False and result.error_code == "APPROVAL_ACTION_MISMATCH"
        print(f"[net intact  ] {label}")
        print(f"               vendor_invocations={calls} success={result.success} code={result.error_code}")
        print(f"               {'PASS refused before vendor call' if intact_ok else 'FAIL'}")

        _, calls_off = await _run_once(pair, disable_net=True)
        load_bearing = calls_off > 0
        print(f"[net disabled] {label}")
        print(f"               vendor_invocations={calls_off}")
        print(f"               {'PASS write proceeds, so the net is load-bearing' if load_bearing else 'FAIL net was never what stopped it'}")
        print()

        if not (intact_ok and load_bearing):
            failures += 1

    print(f"RESULT: {len(PAIRS) - failures}/{len(PAIRS)} vendor pairs proven")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
