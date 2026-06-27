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


def batch_get_values(
    access_token: str,
    spreadsheet_id: str,
    ranges: list[str],
) -> dict[str, Any]:
    if not ranges:
        raise GoogleSheetsAPIError("At least one range is required")
    params = [("ranges", r) for r in ranges]
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values:batchGet",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(
            f"Sheets API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def update_values(
    access_token: str,
    spreadsheet_id: str,
    range_a1: str,
    values: list[list[Any]],
    *,
    value_input_option: str = "USER_ENTERED",
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.put(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_a1}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"valueInputOption": value_input_option},
            json={"values": values},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()


def append_values(
    access_token: str,
    spreadsheet_id: str,
    range_a1: str,
    values: list[list[Any]],
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_a1}:append",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"valueInputOption": "USER_ENTERED"},
            json={"values": values},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()


def create_spreadsheet(access_token: str, *, title: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{SHEETS_API}/spreadsheets",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"properties": {"title": title}},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()


def batch_update_values(
    access_token: str,
    spreadsheet_id: str,
    data: list[dict[str, Any]],
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values:batchUpdate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"valueInputOption": "USER_ENTERED", "data": data},
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()


def add_chart(
    access_token: str,
    spreadsheet_id: str,
    *,
    sheet_id: int,
    chart_spec: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "requests": [
            {
                "addChart": {
                    "chart": {
                        "spec": chart_spec,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0}
                            }
                        },
                    }
                }
            }
        ]
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}:batchUpdate",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()


def create_pivot_table(
    access_token: str,
    spreadsheet_id: str,
    *,
    pivot_spec: dict[str, Any],
) -> dict[str, Any]:
    body = {"requests": [pivot_spec]}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{SHEETS_API}/spreadsheets/{spreadsheet_id}:batchUpdate",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if response.status_code >= 400:
        raise GoogleSheetsAPIError(f"Sheets API {response.status_code}", status_code=response.status_code)
    return response.json()
