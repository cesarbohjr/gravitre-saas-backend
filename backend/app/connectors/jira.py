"""Jira Cloud REST API v3 client (STA-36)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.connectors.jira_oauth import jira_api_base_url

TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class JiraAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _adf_paragraph(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _request(
    method: str,
    cloud_id: str,
    access_token: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{jira_api_base_url(cloud_id=cloud_id)}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, json=json_body)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise JiraAPIError(
                    f"Jira API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()
        except JiraAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise JiraAPIError("Jira API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise JiraAPIError(str(exc)) from exc
    raise JiraAPIError(str(last_error or "Jira request failed"))


def create_issue(
    cloud_id: str,
    access_token: str,
    *,
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue_fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type} if not issue_type.isdigit() else {"id": issue_type},
    }
    if description:
        issue_fields["description"] = _adf_paragraph(description)
    if fields:
        issue_fields.update(fields)
    return _request(
        "POST",
        cloud_id,
        access_token,
        "/issue",
        json_body={"fields": issue_fields},
    )


def assign_issue(
    cloud_id: str,
    access_token: str,
    issue_id_or_key: str,
    account_id: str,
) -> dict[str, Any]:
    return _request(
        "PUT",
        cloud_id,
        access_token,
        f"/issue/{issue_id_or_key}/assignee",
        json_body={"accountId": account_id},
    )


def transition_issue(
    cloud_id: str,
    access_token: str,
    issue_id_or_key: str,
    transition_id: str,
) -> dict[str, Any]:
    return _request(
        "POST",
        cloud_id,
        access_token,
        f"/issue/{issue_id_or_key}/transitions",
        json_body={"transition": {"id": transition_id}},
    )


def add_issue_comment(
    cloud_id: str,
    access_token: str,
    issue_id_or_key: str,
    body: str,
) -> dict[str, Any]:
    return _request(
        "POST",
        cloud_id,
        access_token,
        f"/issue/{issue_id_or_key}/comment",
        json_body={"body": _adf_paragraph(body)},
    )
