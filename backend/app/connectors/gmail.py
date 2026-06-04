"""Gmail API client."""
from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any

import httpx

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
TIMEOUT_SEC = 30.0


class GmailAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _request(
    access_token: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{GMAIL_API}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        raise GmailAPIError(f"Gmail API {response.status_code}: {path}", status_code=response.status_code)
    if not response.text:
        return {}
    return response.json()


def list_messages(
    access_token: str,
    *,
    user_id: str = "me",
    query: str | None = None,
    max_results: int = 25,
) -> dict[str, Any]:
    params: dict[str, Any] = {"maxResults": max_results}
    if query:
        params["q"] = query
    return _request(access_token, "GET", f"/users/{user_id}/messages", params=params)


def get_message(access_token: str, message_id: str, *, user_id: str = "me") -> dict[str, Any]:
    return _request(
        access_token,
        "GET",
        f"/users/{user_id}/messages/{message_id}",
        params={"format": "full"},
    )


def send_message(
    access_token: str,
    *,
    to: str,
    subject: str,
    body: str,
    user_id: str = "me",
) -> dict[str, Any]:
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode().rstrip("=")
    return _request(
        access_token,
        "POST",
        f"/users/{user_id}/messages/send",
        json_body={"raw": raw},
    )
