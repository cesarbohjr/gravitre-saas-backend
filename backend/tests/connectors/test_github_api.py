"""GitHub REST API client tests."""
from __future__ import annotations

from unittest.mock import patch

from app.connectors.github_api import (
    close_pull_request,
    dispatch_workflow,
    get_issue,
    get_repository,
    merge_pull_request,
)


@patch("app.connectors.github_api._request")
def test_get_issue(mock_request):
    mock_request.return_value = {"number": 1, "title": "Bug"}
    issue = get_issue("token", "acme", "repo", 1)
    assert issue["number"] == 1
    mock_request.assert_called_once_with("token", "GET", "/repos/acme/repo/issues/1")


@patch("app.connectors.github_api._request")
def test_get_repository(mock_request):
    mock_request.return_value = {"full_name": "acme/repo"}
    repo = get_repository("token", "acme", "repo")
    assert repo["full_name"] == "acme/repo"


@patch("app.connectors.github_api._request")
def test_dispatch_workflow(mock_request):
    mock_request.return_value = None
    dispatch_workflow("token", "acme", "repo", "ci.yml", ref="main", inputs={"env": "prod"})
    mock_request.assert_called_once()


@patch("app.connectors.github_api._request")
def test_merge_pull_request(mock_request):
    mock_request.return_value = {"merged": True}
    result = merge_pull_request("token", "acme", "repo", 42, merge_method="squash")
    assert result["merged"] is True


@patch("app.connectors.github_api._request")
def test_close_pull_request(mock_request):
    mock_request.return_value = {"state": "closed"}
    pull = close_pull_request("token", "acme", "repo", 7)
    assert pull["state"] == "closed"
