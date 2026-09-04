"""Tests for ConnectWise Manage tool executors."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.connectwise_tools import (
    CONNECTWISE_TOOL_EXECUTORS,
    _exec_connectwise_companies_list,
)
from app.services.tool_types import ToolContext, ToolValidationError


def test_registry_exports_connectwise_actions():
    assert "connectwise.companies.list" in CONNECTWISE_TOOL_EXECUTORS
    assert "connectwise.tickets.create" in CONNECTWISE_TOOL_EXECUTORS


def test_companies_list_requires_connector():
    ctx = ToolContext(
        settings=MagicMock(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )
    ctx.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with pytest.raises(ToolValidationError):
        _exec_connectwise_companies_list(ctx, {})
