"""Google Sheets API client."""
from __future__ import annotations

from typing import Any

import httpx

SHEETS_API = "https://sheets.googleapis.com/v4"
TIMEOUT_SEC = 30.0


class GoogleSheetsAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_spreadsheet(access_token: str, spreadsheet_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "spreadsheetId,properties.title,sheets.properties"},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(
            f"Sheets API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def get_values(
    access_token: str,
    spreadsheet_id: str,
    range_a1: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_a1}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(
            f"Sheets API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()
