"""Marketo REST API client (STA-65)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.connectors.marketo_oauth import marketo_identity_base

TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class MarketoAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _api_base(munchkin_id: str) -> str:
    return f"{marketo_identity_base(munchkin_id)}/rest/v1"


def _request(
    method: str,
    munchkin_id: str,
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    url = f"{_api_base(munchkin_id)}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, json=json_body, params=params)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise MarketoAPIError(
                    f"Marketo API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {}
            data = response.json()
            if isinstance(data, dict) and data.get("success") is False:
                errors = data.get("errors") or []
                raise MarketoAPIError(
                    f"Marketo API error: {errors}",
                    status_code=200,
                    details=errors,
                )
            return data
        except MarketoAPIError:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise MarketoAPIError(str(exc)) from exc
    raise MarketoAPIError(str(last_error or "Marketo request failed"))


def get_lead(
    access_token: str,
    munchkin_id: str,
    *,
    lead_id: str | None = None,
    email: str | None = None,
    filter_type: str | None = None,
    filter_values: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if lead_id:
        params["filterType"] = "id"
        params["filterValues"] = str(lead_id)
    elif email:
        params["filterType"] = "email"
        params["filterValues"] = str(email)
    elif filter_type and filter_values:
        params["filterType"] = filter_type
        params["filterValues"] = filter_values
    else:
        raise MarketoAPIError("lead_id, email, or filter_type/filter_values required")
    return _request("GET", munchkin_id, access_token, "/leads.json", params=params)


def update_leads(
    access_token: str,
    munchkin_id: str,
    *,
    action: str,
    leads: list[dict[str, Any]],
    lookup_field: str = "email",
    async_request: bool = False,
) -> dict[str, Any]:
    if not leads:
        raise MarketoAPIError("leads array is required")
    body: dict[str, Any] = {
        "action": action,
        "lookupField": lookup_field,
        "input": leads,
    }
    if async_request:
        body["asyncProcessing"] = True
    return _request("POST", munchkin_id, access_token, "/leads.json", json_body=body)


def list_campaigns(
    access_token: str,
    munchkin_id: str,
    *,
    is_request: bool | None = None,
    offset: int | None = None,
    max_return: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if is_request is not None:
        params["isRequest"] = str(is_request).lower()
    if offset is not None:
        params["offset"] = offset
    if max_return is not None:
        params["maxReturn"] = max_return
    return _request("GET", munchkin_id, access_token, "/campaigns.json", params=params or None)


def get_program_status(
    access_token: str,
    munchkin_id: str,
    program_id: str | int,
) -> dict[str, Any]:
    return _request("GET", munchkin_id, access_token, f"/programs/{program_id}.json")


def add_to_static_list(
    access_token: str,
    munchkin_id: str,
    list_id: str | int,
    *,
    lead_ids: list[str | int] | None = None,
    emails: list[str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if lead_ids:
        body["id"] = [int(x) for x in lead_ids]
    elif emails:
        body["email"] = list(emails)
    else:
        raise MarketoAPIError("lead_ids or emails required")
    return _request("POST", munchkin_id, access_token, f"/lists/{list_id}/leads.json", json_body=body)


def get_static_list_leads(
    access_token: str,
    munchkin_id: str,
    list_id: str | int,
    *,
    batch_size: int | None = None,
    next_page_token: str | None = None,
    fields: str | None = None,
) -> dict[str, Any]:
    """GET /rest/v1/lists/{listId}/leads.json — membership read for F6 verify."""
    params: dict[str, Any] = {}
    if batch_size is not None:
        params["batchSize"] = max(1, min(int(batch_size), 300))
    if next_page_token:
        params["nextPageToken"] = next_page_token
    if fields:
        params["fields"] = fields
    return _request(
        "GET",
        munchkin_id,
        access_token,
        f"/lists/{list_id}/leads.json",
        params=params or None,
    )
