from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.connectors.jira import JiraAPIError, create_issue, get_issue, search_issues


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


def test_get_issue_passes_fields_param():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"key":"ENG-1"}'
    mock_response.json.return_value = {"key": "ENG-1"}
    with patch("app.connectors.jira.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        get_issue("cloud-abc", "token", "ENG-1", fields=["summary", "status"])
    call_kwargs = client_cls.return_value.__enter__.return_value.request.call_args.kwargs
    assert call_kwargs["params"]["fields"] == "summary,status"


def test_search_issues_posts_jql():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"issues":[]}'
    mock_response.json.return_value = {"issues": []}
    with patch("app.connectors.jira.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        search_issues("cloud-abc", "token", 'project = "ENG"', max_results=25)
    body = client_cls.return_value.__enter__.return_value.request.call_args.kwargs["json"]
    assert body["jql"] == 'project = "ENG"'
    assert body["maxResults"] == 25
