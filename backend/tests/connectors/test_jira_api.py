from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.connectors.jira import JiraAPIError, create_issue


def test_create_issue_calls_jira_api():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"id":"10001","key":"ENG-1"}'
    mock_response.json.return_value = {"id": "10001", "key": "ENG-1"}
    with patch("app.connectors.jira.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        result = create_issue(
            "cloud-abc",
            "token",
            project_key="ENG",
            summary="Test",
            issue_type="Task",
            description="Details",
        )
    assert result["key"] == "ENG-1"


def test_create_issue_maps_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.side_effect = ValueError()
    with patch("app.connectors.jira.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        try:
            create_issue("cloud-abc", "token", project_key="ENG", summary="Test", issue_type="Task")
        except JiraAPIError as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected JiraAPIError")
