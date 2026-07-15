"""SEMrush / Ahrefs tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.ahrefs_tools import AHREFS_TOOL_EXECUTORS
from app.services.semrush_tools import SEMRUSH_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx(vendor: str = "semrush") -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id=f"conn-{vendor}",
        environment_name="production",
    )


def test_seo_v1_tools_registered():
    for action in list(SEMRUSH_TOOL_EXECUTORS) + list(AHREFS_TOOL_EXECUTORS):
        assert action in list_registered_actions()


@patch("app.services.semrush_tools.enforce_rate_limit")
@patch("app.services.semrush_tools.resolve_semrush_connector")
@patch("app.services.semrush_tools.domain_overview")
def test_semrush_domain_overview(mock_api, mock_session, _rate):
    mock_session.return_value = ("conn-semrush", "key")
    mock_api.return_value = {"row_count": 1}
    result = SEMRUSH_TOOL_EXECUTORS["semrush.domain.overview"](_ctx(), {"domain": "example.com"})
    assert result.success
    mock_api.assert_called_once()


@patch("app.services.ahrefs_tools.enforce_rate_limit")
@patch("app.services.ahrefs_tools.resolve_ahrefs_connector")
@patch("app.services.ahrefs_tools.domain_rating")
def test_ahrefs_domain_rating(mock_api, mock_session, _rate):
    mock_session.return_value = ("conn-ahrefs", "key")
    mock_api.return_value = {"data": {"domain_rating": 70}}
    result = AHREFS_TOOL_EXECUTORS["ahrefs.domain.rating"](_ctx("ahrefs"), {"target": "example.com"})
    assert result.success
    mock_api.assert_called_once()
