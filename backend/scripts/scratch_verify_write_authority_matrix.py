"""Scratch probe: does every write entry point share one authority?

Phase 6 asks whether MCP-sourced actions, extension-bridge writes, and
workflow-step writes route through the same catalog_write_authority /
react_write_gate path already proven for chat direct-create.

Reports what each surface actually does. Does not assume parity.

Run: python scripts/scratch_verify_write_authority_matrix.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.catalog_write_authority import (  # noqa: E402
    invoke_action_requires_write_approval,
    mcp_tool_requires_write_approval,
)
from app.services.react_write_gate import (  # noqa: E402
    PLATFORM_WRITE_TOOLS,
    tool_requires_user_write_approval,
)
from app.services.tool_registry import get_tool_registry  # noqa: E402

WRITE_SAMPLES = [
    ("hubspot_contacts_create", "hubspot.contacts.create"),
    ("slack_post_message", "slack.post_message"),
    ("notion_pages_create", "notion.pages.create"),
]
READ_SAMPLE = ("hubspot_contacts_get", "hubspot.contacts.get")

results: list[tuple[str, bool, str]] = []


def record(surface: str, ok: bool, detail: str) -> None:
    results.append((surface, ok, detail))
    print(f"[{'PASS' if ok else 'GAP '}] {surface}")
    print(f"        {detail}\n")


def main() -> int:
    registry = get_tool_registry()

    # ---- Baseline: chat / ReAct direct-create (the already-proven case) ----
    gated = [t for t, _ in WRITE_SAMPLES if tool_requires_user_write_approval(t, registry)[0]]
    read_gated = tool_requires_user_write_approval(READ_SAMPLE[0], registry)[0]
    record(
        "chat/ReAct direct-create",
        len(gated) == len(WRITE_SAMPLES) and not read_gated,
        f"writes gated {len(gated)}/{len(WRITE_SAMPLES)}; read {READ_SAMPLE[0]} gated={read_gated}",
    )

    # ---- MCP-sourced ----
    mcp_registry = MagicMock()
    mcp_registry.get_mcp_tool_meta.return_value = {
        "capability_tier": "write",
        "requires_approval": True,
        "read_only_hint": False,
        "destructive_hint": False,
        "label": "Create record",
    }
    mcp_write = tool_requires_user_write_approval("mcp_acme_create_record", mcp_registry)

    mcp_read_registry = MagicMock()
    mcp_read_registry.get_mcp_tool_meta.return_value = {
        "capability_tier": "read",
        "requires_approval": False,
        "read_only_hint": True,
        "destructive_hint": False,
        "label": "List records",
    }
    mcp_read = tool_requires_user_write_approval("mcp_acme_list_records", mcp_read_registry)

    direct = mcp_tool_requires_write_approval(
        capability_tier="write", requires_approval=True, read_only_hint=False, destructive_hint=False
    )
    record(
        "MCP-sourced",
        mcp_write[0] is True and mcp_read[0] is False and direct is True,
        f"write gated={mcp_write[0]} read gated={mcp_read[0]}; "
        f"react_write_gate delegates to catalog_write_authority.mcp_tool_requires_write_approval={direct}",
    )

    # ---- Extension bridge ----
    import app.services.extension_bridge_service as ext

    bridge_src = inspect.getsource(ext)
    bridge_uses_authority = "invoke_action_requires_write_approval" in bridge_src
    bridge_decisions = [invoke_action_requires_write_approval(a) for _, a in WRITE_SAMPLES]
    bridge_read = invoke_action_requires_write_approval(READ_SAMPLE[1])
    # Parity means the bridge and chat agree action-for-action.
    chat_decisions = [tool_requires_user_write_approval(t, registry)[0] for t, _ in WRITE_SAMPLES]
    record(
        "extension-bridge",
        bridge_uses_authority and all(bridge_decisions) and not bridge_read
        and bridge_decisions == chat_decisions,
        f"imports catalog_write_authority={bridge_uses_authority}; "
        f"writes gated={bridge_decisions} read gated={bridge_read}; agrees with chat={bridge_decisions == chat_decisions}",
    )

    # ---- Workflow steps ----
    import app.workflows.handlers as handlers
    from app.services.tool_service import invoke_tool

    handlers_src = inspect.getsource(handlers)
    invoke_src = inspect.getsource(invoke_tool)
    step_consults_authority = (
        "catalog_write_authority" in handlers_src
        or "requires_write_approval" in handlers_src
        or "catalog_write_authority" in invoke_src
        or "requires_write_approval" in invoke_src
    )
    boundary_gated = "assistant_execute_workflow" in PLATFORM_WRITE_TOOLS
    record(
        "workflow-step",
        step_consults_authority,
        "per-step approval authority consulted="
        f"{step_consults_authority} (handlers call invoke_tool directly); "
        f"gated instead at the execution boundary: assistant_execute_workflow in PLATFORM_WRITE_TOOLS={boundary_gated}",
    )

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"RESULT: {passed}/{len(results)} surfaces share the per-action write-approval authority")
    for surface, ok, _ in results:
        if not ok:
            print(f"  GAP: {surface}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
