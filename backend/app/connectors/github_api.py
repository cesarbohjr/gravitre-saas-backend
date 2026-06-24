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
