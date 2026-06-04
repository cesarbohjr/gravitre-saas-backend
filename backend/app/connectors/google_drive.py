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
