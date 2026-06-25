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


def list_joined_teams(access_token: str) -> dict[str, Any]:
    return _request(access_token, "GET", "/me/joinedTeams")


def list_team_channels(access_token: str, *, team_id: str) -> dict[str, Any]:
    if not team_id:
        raise Microsoft365APIError("team_id is required")
    return _request(access_token, "GET", f"/teams/{team_id}/channels")


def list_channel_messages(
    access_token: str,
    *,
    team_id: str,
    channel_id: str,
    top: int = 25,
) -> dict[str, Any]:
    if not team_id or not channel_id:
        raise Microsoft365APIError("team_id and channel_id are required")
    params: dict[str, Any] = {"$top": min(max(int(top), 1), 50)}
    return _request(
        access_token,
        "GET",
        f"/teams/{team_id}/channels/{channel_id}/messages",
        params=params,
    )


def create_online_meeting(
    access_token: str,
    *,
    subject: str,
    start_datetime: str,
    end_datetime: str,
) -> dict[str, Any]:
    if not subject or not start_datetime or not end_datetime:
        raise Microsoft365APIError("subject, start_datetime, and end_datetime are required")
    body = {
        "subject": subject,
        "startDateTime": start_datetime,
        "endDateTime": end_datetime,
    }
    return _request(access_token, "POST", "/me/onlineMeetings", json_body=body)


def add_channel_tab(
    access_token: str,
    *,
    team_id: str,
    channel_id: str,
    display_name: str,
    content_url: str,
) -> dict[str, Any]:
    if not team_id or not channel_id or not display_name or not content_url:
        raise Microsoft365APIError("team_id, channel_id, display_name, and content_url are required")
    body = {
        "displayName": display_name,
        "teamsApp": {"id": "com.microsoft.teamspace.tab.web"},
        "configuration": {"entityId": None, "contentUrl": content_url, "websiteUrl": content_url},
    }
    return _request(
        access_token,
        "POST",
        f"/teams/{team_id}/channels/{channel_id}/tabs",
        json_body=body,
    )


def add_team_member(
    access_token: str,
    *,
    team_id: str,
    user_id: str,
    roles: list[str] | None = None,
) -> dict[str, Any]:
    if not team_id or not user_id:
        raise Microsoft365APIError("team_id and user_id are required")
    body = {
        "@odata.type": "#microsoft.graph.aadUserConversationMember",
        "roles": roles or ["member"],
        "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
    }
    return _request(access_token, "POST", f"/teams/{team_id}/members", json_body=body)


def set_user_presence(
    access_token: str,
    *,
    availability: str,
    activity: str,
    expiration_duration: str = "PT1H",
) -> dict[str, Any]:
    body = {
        "availability": availability,
        "activity": activity,
        "expirationDuration": expiration_duration,
    }
    return _request(access_token, "POST", "/me/presence/setUserPreferredPresence", json_body=body)


def search_sharepoint_sites(access_token: str, *, query: str, top: int = 25) -> dict[str, Any]:
    if not query:
        raise Microsoft365APIError("query is required")
    return _request(
        access_token,
        "GET",
        "/sites",
        params={"search": query, "$top": min(max(int(top), 1), 50)},
    )


def list_site_drives(access_token: str, *, site_id: str) -> dict[str, Any]:
    if not site_id:
        raise Microsoft365APIError("site_id is required")
    return _request(access_token, "GET", f"/sites/{site_id}/drives")


def list_drive_items(
    access_token: str,
    *,
    drive_id: str,
    item_id: str | None = None,
    top: int = 25,
) -> dict[str, Any]:
    if not drive_id:
        raise Microsoft365APIError("drive_id is required")
    if item_id:
        path = f"/drives/{drive_id}/items/{item_id}/children"
    else:
        path = f"/drives/{drive_id}/root/children"
    return _request(access_token, "GET", path, params={"$top": min(max(int(top), 1), 50)})


def upload_drive_item_content(
    access_token: str,
    *,
    drive_id: str,
    filename: str,
    content: str | bytes,
    parent_item_id: str | None = None,
) -> dict[str, Any]:
    if not drive_id or not filename:
        raise Microsoft365APIError("drive_id and filename are required")
    if parent_item_id:
        path = f"/drives/{drive_id}/items/{parent_item_id}:/{filename}:/content"
    else:
        path = f"/drives/{drive_id}/root:/{filename}:/content"
    url = f"{GRAPH_API}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = content.encode("utf-8") if isinstance(content, str) else content
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.put(url, headers=headers, content=data)
    if response.status_code >= 400:
        raise Microsoft365APIError(
            f"Microsoft Graph {response.status_code}: sharepoint upload",
            status_code=response.status_code,
        )
    return response.json() if response.text else {}


def delete_drive_item(access_token: str, *, drive_id: str, item_id: str) -> dict[str, Any]:
    if not drive_id or not item_id:
        raise Microsoft365APIError("drive_id and item_id are required")
    return _request(access_token, "DELETE", f"/drives/{drive_id}/items/{item_id}")
