"""STA-115: real estate tool executors."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.real_estate_tools import REAL_ESTATE_TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=MagicMock(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )


def test_mls_note_tool():
    result = REAL_ESTATE_TOOL_EXECUTORS["real_estate.mls.note"](
        _ctx(),
        {"property_address": "100 Oak Ave", "list_price": "600000"},
    )
    assert result.success
    assert len(result.data["sections"]) >= 3


def test_handoff_brief_tool():
    result = REAL_ESTATE_TOOL_EXECUTORS["real_estate.handoff.brief"](
        _ctx(),
        {"buyer_name": "Alex", "property_address": "100 Oak Ave"},
    )
    assert result.success
    assert len(result.data["checklist"]) >= 3
