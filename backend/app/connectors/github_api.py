"""GitHub REST API client (STA-22)."""
from __future__ import annotations

from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
TIMEOUT_SEC = 30.0


class GitHubAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    token: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{GITHUB_API}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise GitHubAPIError(
            f"GitHub API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def list_pull_requests(
    token: str,
    owner: str,
    repo: str,
    *,
    state: str = "open",
    per_page: int = 10,
) -> list[dict[str, Any]]:
    data = _request(
        token,
        "GET",
        f"/repos/{owner}/{repo}/pulls",
        params={"state": state, "per_page": min(per_page, 100)},
    )
    return list(data) if isinstance(data, list) else []


def get_pull_request(
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
) -> dict[str, Any]:
    return _request(token, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}")


def close_pull_request(
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
) -> dict[str, Any]:
    return _request(
        token,
        "PATCH",
        f"/repos/{owner}/{repo}/pulls/{pull_number}",
        json_body={"state": "closed"},
    )


def get_issue(
    token: str,
    owner: str,
    repo: str,
    issue_number: int,
) -> dict[str, Any]:
    return _request(token, "GET", f"/repos/{owner}/{repo}/issues/{issue_number}")


def list_issues(
    token: str,
    owner: str,
    repo: str,
    *,
    state: str = "open",
    per_page: int = 30,
) -> list[dict[str, Any]]:
    data = _request(
        token,
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": state, "per_page": min(per_page, 100)},
    )
    return list(data) if isinstance(data, list) else []


def get_repository(token: str, owner: str, repo: str) -> dict[str, Any]:
    return _request(token, "GET", f"/repos/{owner}/{repo}")


def create_issue(
    token: str,
    owner: str,
    repo: str,
    *,
    title: str,
    body: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"title": title}
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = labels
    return _request(token, "POST", f"/repos/{owner}/{repo}/issues", json_body=payload)


def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    *,
    title: str,
    head: str,
    base: str,
    body: str | None = None,
    draft: bool = False,
) -> dict[str, Any]:
    """Create a pull request — POST /repos/{owner}/{repo}/pulls (Batch 1)."""
    if not title or not head or not base:
        raise GitHubAPIError("title, head, and base are required")
    payload: dict[str, Any] = {
        "title": title,
        "head": head,
        "base": base,
        "draft": bool(draft),
    }
    if body:
        payload["body"] = body
    return _request(token, "POST", f"/repos/{owner}/{repo}/pulls", json_body=payload)


def list_workflow_runs(
    token: str,
    owner: str,
    repo: str,
    *,
    per_page: int = 10,
    status: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """List workflow runs — GET /repos/{owner}/{repo}/actions/runs (Batch 1)."""
    params: dict[str, Any] = {"per_page": min(max(int(per_page), 1), 100)}
    if status:
        params["status"] = status
    if branch:
        params["branch"] = branch
    return _request(token, "GET", f"/repos/{owner}/{repo}/actions/runs", params=params)


def update_issue(
    token: str,
    owner: str,
    repo: str,
    issue_number: int,
    *,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Update an issue — PATCH /repos/{owner}/{repo}/issues/{number} (Batch 1)."""
    if not issue_number:
        raise GitHubAPIError("issue_number is required")
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state
    if labels is not None:
        payload["labels"] = labels
    if not payload:
        raise GitHubAPIError("at least one update field is required")
    return _request(
        token,
        "PATCH",
        f"/repos/{owner}/{repo}/issues/{int(issue_number)}",
        json_body=payload,
    )


def create_issue_comment(
    token: str,
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
) -> dict[str, Any]:
    return _request(
        token,
        "POST",
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        json_body={"body": body},
    )


def request_pull_request_reviewer(
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
    reviewers: list[str],
) -> dict[str, Any]:
    return _request(
        token,
        "POST",
        f"/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers",
        json_body={"reviewers": reviewers},
    )


def dispatch_workflow(
    token: str,
    owner: str,
    repo: str,
    workflow_id: str | int,
    *,
    ref: str,
    inputs: dict[str, str] | None = None,
) -> None:
    payload: dict[str, Any] = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs
    _request(
        token,
        "POST",
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        json_body=payload,
    )


def merge_pull_request(
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
    *,
    commit_title: str | None = None,
    commit_message: str | None = None,
    merge_method: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message
    if merge_method:
        payload["merge_method"] = merge_method
    return _request(
        token,
        "PUT",
        f"/repos/{owner}/{repo}/pulls/{pull_number}/merge",
        json_body=payload or None,
    )


def create_release(
    token: str,
    owner: str,
    repo: str,
    *,
    tag_name: str,
    name: str | None = None,
    body: str | None = None,
    draft: bool = False,
    prerelease: bool = False,
    target_commitish: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"tag_name": tag_name, "draft": draft, "prerelease": prerelease}
    if name:
        payload["name"] = name
    if body:
        payload["body"] = body
    if target_commitish:
        payload["target_commitish"] = target_commitish
    return _request(token, "POST", f"/repos/{owner}/{repo}/releases", json_body=payload)
