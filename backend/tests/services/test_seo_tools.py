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


@patch("app.services.semrush_tools.enforce_rate_limit")
@patch("app.services.semrush_tools.resolve_semrush_connector")
@patch("app.services.semrush_tools.create_project")
def test_semrush_projects_create(mock_api, mock_session, _rate):
    mock_session.return_value = ("conn-semrush", "key")
    mock_api.return_value = {"project_name": "Demo"}
    result = SEMRUSH_TOOL_EXECUTORS["semrush.projects.create"](
        _ctx(), {"name": "Demo", "url": "https://example.com"}
    )
    assert result.success
    mock_api.assert_called_once()


@patch("app.services.ahrefs_tools.enforce_rate_limit")
@patch("app.services.ahrefs_tools.resolve_ahrefs_connector")
@patch("app.services.ahrefs_tools.create_project")
def test_ahrefs_projects_create(mock_api, mock_session, _rate):
    mock_session.return_value = ("conn-ahrefs", "key")
    mock_api.return_value = {"project_name": "Demo"}
    result = AHREFS_TOOL_EXECUTORS["ahrefs.projects.create"](
        _ctx("ahrefs"), {"name": "Demo", "url": "https://example.com"}
    )
    assert result.success
    mock_api.assert_called_once()


def test_ahrefs_workflow_schemas_registered():
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema

    assert get_workflow_schema("ahrefs.projects.create") is not None
    assert get_workflow_schema("ahrefs.rank_tracker.add") is not None
