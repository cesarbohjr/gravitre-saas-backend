"""Zendesk Support API client (STA-21)."""
from __future__ import annotations

import base64
from typing import Any

import httpx

TIMEOUT_SEC = 30.0


class ZendeskAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _auth_header(email: str, api_token: str) -> str:
    raw = f"{email}/token:{api_token}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _request(
    subdomain: str,
    email: str,
    api_token: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://{subdomain}.zendesk.com/api/v2{path}"
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ZendeskAPIError(
            f"Zendesk API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def get_ticket(subdomain: str, email: str, api_token: str, ticket_id: int | str) -> dict[str, Any]:
    data = _request(subdomain, email, api_token, "GET", f"/tickets/{ticket_id}.json")
    return data.get("ticket") or data


def create_ticket(
    subdomain: str,
    email: str,
    api_token: str,
    *,
    subject: str,
    comment: str,
    requester_email: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    ticket: dict[str, Any] = {
        "subject": subject,
        "comment": {"body": comment},
    }
    if requester_email:
        ticket["requester"] = {"email": requester_email}
    if priority:
        ticket["priority"] = priority
    if tags:
        ticket["tags"] = tags
    data = _request(subdomain, email, api_token, "POST", "/tickets.json", json_body={"ticket": ticket})
    return data.get("ticket") or data


def update_ticket(
    subdomain: str,
    email: str,
    api_token: str,
    ticket_id: int | str,
    *,
    status: str | None = None,
    priority: str | None = None,
    comment: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    ticket: dict[str, Any] = {}
    if status:
        ticket["status"] = status
    if priority:
        ticket["priority"] = priority
    if tags is not None:
        ticket["tags"] = tags
    if comment:
        ticket["comment"] = {"body": comment, "public": True}
    data = _request(
        subdomain,
        email,
        api_token,
        "PUT",
        f"/tickets/{ticket_id}.json",
        json_body={"ticket": ticket},
    )
    return data.get("ticket") or data


def search_tickets(
    subdomain: str,
    email: str,
    api_token: str,
    *,
    query: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Zendesk search API — e.g. type:ticket status:solved updated>YYYY-MM-DD."""
    if not query.strip():
        raise ZendeskAPIError("search query is required")
    per_page = min(max(int(limit), 1), 100)
    data = _request(
        subdomain,
        email,
        api_token,
        "GET",
        "/search.json",
        params={"query": query, "per_page": per_page},
    )
    tickets: list[dict[str, Any]] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        ticket = item.get("ticket") if item.get("result_type") == "ticket" else item
        if isinstance(ticket, dict):
            tickets.append(dict(ticket))
    return tickets


def list_resolved_tickets_since(
    subdomain: str,
    email: str,
    api_token: str,
    *,
    since_date: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Resolved/solved tickets updated on or after since_date (YYYY-MM-DD)."""
    q = f"type:ticket status:solved updated>={since_date}"
    return search_tickets(subdomain, email, api_token, query=q, limit=limit)


def add_ticket_tags(
    subdomain: str,
    email: str,
    api_token: str,
    ticket_id: int | str,
    tags: list[str],
) -> dict[str, Any]:
    data = _request(
        subdomain,
        email,
        api_token,
        "PUT",
        f"/tickets/{ticket_id}/tags.json",
        json_body={"tags": tags},
    )
    return data.get("tags") or data
