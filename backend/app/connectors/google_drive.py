"""Google Drive API client."""
from __future__ import annotations

from typing import Any

import httpx

DRIVE_API = "https://www.googleapis.com/drive/v3"
TIMEOUT_SEC = 30.0


class GoogleDriveAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def list_files(
    access_token: str,
    *,
    page_size: int = 25,
    query: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "pageSize": page_size,
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink),nextPageToken",
    }
    if query:
        params["q"] = query
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DRIVE_API}/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(
            f"Drive API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def get_file(access_token: str, file_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DRIVE_API}/files/{file_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "id,name,mimeType,modifiedTime,webViewLink,size"},
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(
            f"Drive API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def list_permissions(access_token: str, file_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DRIVE_API}/files/{file_id}/permissions",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "permissions(id,type,role,emailAddress,domain)"},
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(
            f"Drive API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def create_file(
    access_token: str,
    *,
    name: str,
    mime_type: str = "application/octet-stream",
    content: str | bytes | None = None,
    parents: list[str] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"name": name, "mimeType": mime_type}
    if parents:
        metadata["parents"] = parents
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        if content is None:
            response = client.post(f"{DRIVE_API}/files", headers=headers, json=metadata)
        else:
            data = content.encode("utf-8") if isinstance(content, str) else content
            response = client.post(
                f"{DRIVE_API}/files",
                headers=headers,
                params={"uploadType": "media"},
                content=data,
            )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.json()


def update_file(
    access_token: str,
    file_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if description:
        body["description"] = description
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.patch(
            f"{DRIVE_API}/files/{file_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.json()


def create_permission(
    access_token: str,
    file_id: str,
    *,
    role: str,
    type: str = "user",
    email_address: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"role": role, "type": type}
    if email_address:
        body["emailAddress"] = email_address
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{DRIVE_API}/files/{file_id}/permissions",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.json()


def export_file(
    access_token: str,
    file_id: str,
    *,
    mime_type: str = "application/pdf",
) -> bytes:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DRIVE_API}/files/{file_id}/export",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"mimeType": mime_type},
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.content


def list_changes(
    access_token: str,
    *,
    page_token: str | None = None,
    page_size: int = 25,
) -> dict[str, Any]:
    params: dict[str, Any] = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DRIVE_API}/changes",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.json()


def batch_permissions(
    access_token: str,
    *,
    requests: list[dict[str, Any]],
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            "https://www.googleapis.com/batch/drive/v3",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"requests": requests},
        )
    if response.status_code >= 400:
        raise GoogleDriveAPIError(f"Drive API {response.status_code}", status_code=response.status_code)
    return response.json() if response.text else {}
