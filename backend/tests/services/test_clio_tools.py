"""STA-114: Clio tool executors."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.clio_tools import CLIO_TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=MagicMock(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-clio",
    )


@patch("app.services.clio_tools.enforce_rate_limit")
@patch("app.services.clio_tools.ensure_clio_session")
def test_clio_contacts_search_demo(mock_session, _rate):
    mock_session.return_value = ("conn-clio", None, True)
    executor = CLIO_TOOL_EXECUTORS["clio.contacts.search"]
    result = executor(_ctx(), {"query": "Acme"})
    assert result.success
    assert result.data["data"]
    assert result.data["meta"]["demo"] is True


@patch("app.services.clio_tools.enforce_rate_limit")
@patch("app.services.clio_tools.ensure_clio_session")
def test_clio_matters_search_demo(mock_session, _rate):
    mock_session.return_value = ("conn-clio", None, True)
    executor = CLIO_TOOL_EXECUTORS["clio.matters.search"]
    result = executor(_ctx(), {"client_id": "1001"})
    assert result.success
    assert all(str(m["client"]["id"]) == "1001" for m in result.data["data"])


@patch("app.services.clio_tools.enforce_rate_limit")
@patch("app.services.clio_tools.ensure_clio_session")
def test_clio_conflict_checklist(mock_session, _rate):
    mock_session.return_value = ("conn-clio", None, True)
    executor = CLIO_TOOL_EXECUTORS["clio.conflict.checklist"]
    result = executor(_ctx(), {"prospect_name": "Jane Rivera"})
    assert result.success
    assert len(result.data["checklist"]) >= 3


@patch("app.services.clio_tools.enforce_rate_limit")
@patch("app.services.clio_tools.ensure_clio_session")
def test_clio_intake_tasks(mock_session, _rate):
    mock_session.return_value = ("conn-clio", None, True)
    executor = CLIO_TOOL_EXECUTORS["clio.intake.tasks"]
    result = executor(_ctx(), {"matter_name": "Test matter"})
    assert result.success
    assert len(result.data["tasks"]) >= 3
