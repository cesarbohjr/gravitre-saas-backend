"""Google Docs API client."""
from __future__ import annotations

from typing import Any

import httpx

DOCS_API = "https://docs.googleapis.com/v1"
TIMEOUT_SEC = 30.0


class GoogleDocsAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_document(access_token: str, document_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{DOCS_API}/documents/{document_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise GoogleDocsAPIError(
            f"Docs API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def document_plain_text(doc: dict[str, Any]) -> str:
    """Best-effort plain text from Docs API body."""
    chunks: list[str] = []

    def walk(elements: list[Any]) -> None:
        for el in elements:
            if not isinstance(el, dict):
                continue
            para = el.get("paragraph")
            if para:
                for pe in para.get("elements") or []:
                    tr = (pe.get("textRun") or {}).get("content")
                    if tr:
                        chunks.append(str(tr))
            table = el.get("table")
            if table:
                for row in table.get("tableRows") or []:
                    for cell in row.get("tableCells") or []:
                        walk(cell.get("content") or [])

    body = doc.get("body") or {}
    walk(body.get("content") or [])
    return "".join(chunks).strip()
