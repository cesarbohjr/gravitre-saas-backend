"""Microsoft Graph API client for Microsoft 365 connector tools."""
from __future__ import annotations

from typing import Any

import httpx

GRAPH_API = "https://graph.microsoft.com/v1.0"
TIMEOUT_SEC = 30.0


class Microsoft365APIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    access_token: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{GRAPH_API}{path}"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise Microsoft365APIError(
            f"Microsoft Graph {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def get_user(access_token: str, *, user_id: str = "me") -> dict[str, Any]:
    return _request(access_token, "GET", f"/users/{user_id}")


def list_mail_messages(
    access_token: str,
    *,
    user_id: str = "me",
    top: int = 25,
    filter_query: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "$top": min(max(int(top), 1), 50),
        "$orderby": "receivedDateTime desc",
    }
    if filter_query:
        params["$filter"] = filter_query
    return _request(access_token, "GET", f"/users/{user_id}/messages", params=params)


def list_calendar_events(
    access_token: str,
    *,
    user_id: str = "me",
    top: int = 25,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "$top": min(max(int(top), 1), 50),
        "$orderby": "start/dateTime",
    }
    if start_datetime and end_datetime:
        params["$filter"] = (
            f"start/dateTime ge '{start_datetime}' and end/dateTime le '{end_datetime}'"
        )
    return _request(access_token, "GET", f"/users/{user_id}/calendar/events", params=params)


def send_mail(
    access_token: str,
    *,
    user_id: str = "me",
    subject: str,
    body: str,
    to_recipients: list[str],
    content_type: str = "Text",
) -> dict[str, Any]:
    if not subject or not body or not to_recipients:
        raise Microsoft365APIError("send_mail requires subject, body, and to_recipients")
    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to_recipients],
        },
        "saveToSentItems": True,
    }
    return _request(access_token, "POST", f"/users/{user_id}/sendMail", json_body=message)


def create_calendar_event(
    access_token: str,
    *,
    user_id: str = "me",
    subject: str,
    start_datetime: str,
    end_datetime: str,
    body: str | None = None,
    timezone: str = "UTC",
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "subject": subject,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
    }
    if body:
        event["body"] = {"contentType": "Text", "content": body}
    return _request(access_token, "POST", f"/users/{user_id}/calendar/events", json_body=event)


def upload_drive_file(
    access_token: str,
    *,
    user_id: str = "me",
    filename: str,
    content: str | bytes,
    parent_id: str | None = None,
) -> dict[str, Any]:
    if not filename:
        raise Microsoft365APIError("filename is required")
    path = f"/users/{user_id}/drive/root:/{filename}:/content"
    if parent_id:
        path = f"/users/{user_id}/drive/items/{parent_id}:/{filename}:/content"
    url = f"{GRAPH_API}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = content.encode("utf-8") if isinstance(content, str) else content
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.put(url, headers=headers, content=data)
    if response.status_code >= 400:
        raise Microsoft365APIError(
            f"Microsoft Graph {response.status_code}: drive upload",
            status_code=response.status_code,
        )
    return response.json() if response.text else {}


def update_excel_range(
    access_token: str,
    *,
    user_id: str = "me",
    item_id: str,
    worksheet: str,
    address: str,
    values: list[list[Any]],
) -> dict[str, Any]:
    body = {"values": values}
    return _request(
        access_token,
        "PATCH",
        f"/users/{user_id}/drive/items/{item_id}/workbook/worksheets/{worksheet}/range(address='{address}')",
        json_body=body,
    )


def post_teams_channel_message(
    access_token: str,
    *,
    team_id: str,
    channel_id: str,
    content: str,
) -> dict[str, Any]:
    body = {"body": {"content": content}}
    return _request(
        access_token,
        "POST",
        f"/teams/{team_id}/channels/{channel_id}/messages",
        json_body=body,
    )


def batch_send_mail(
    access_token: str,
    *,
    user_id: str = "me",
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    if not messages:
        raise Microsoft365APIError("messages list is required")
    requests_payload = []
    for idx, msg in enumerate(messages):
        requests_payload.append(
            {
                "id": str(idx + 1),
                "method": "POST",
                "url": f"/users/{user_id}/sendMail",
                "headers": {"Content-Type": "application/json"},
                "body": msg if "message" in msg else {"message": msg},
            }
        )
    return _request(access_token, "POST", "/$batch", json_body={"requests": requests_payload})
