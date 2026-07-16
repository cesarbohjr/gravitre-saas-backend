"""GitHub REST API client tests."""
from __future__ import annotations

from unittest.mock import patch

from app.connectors.github_api import (
    close_pull_request,
    create_pull_request,
    dispatch_workflow,
    get_issue,
    get_repository,
    list_workflow_runs,
    merge_pull_request,
    update_issue,
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


@patch("app.connectors.github_api._request")
def test_create_pull_request(mock_request):
    mock_request.return_value = {"number": 9, "html_url": "https://github.com/acme/repo/pull/9"}
    pull = create_pull_request(
        "token", "acme", "repo", title="Add tip", head="feat", base="main", draft=True
    )
    assert pull["number"] == 9
    mock_request.assert_called_once()
    assert mock_request.call_args.args[1:] == ("POST", "/repos/acme/repo/pulls")


@patch("app.connectors.github_api._request")
def test_list_workflow_runs(mock_request):
    mock_request.return_value = {"total_count": 1, "workflow_runs": [{"id": 1}]}
    data = list_workflow_runs("token", "acme", "repo", per_page=5)
    assert data["total_count"] == 1
    mock_request.assert_called_once_with(
        "token",
        "GET",
        "/repos/acme/repo/actions/runs",
        params={"per_page": 5},
    )


@patch("app.connectors.github_api._request")
def test_update_issue(mock_request):
    mock_request.return_value = {"number": 3, "state": "closed"}
    issue = update_issue("token", "acme", "repo", 3, state="closed")
    assert issue["state"] == "closed"
