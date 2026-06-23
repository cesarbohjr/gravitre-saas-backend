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


def batch_get_documents(access_token: str, document_ids: list[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document_id in document_ids:
        doc_id = str(document_id).strip()
        if not doc_id:
            continue
        docs.append(get_document(access_token, doc_id))
    return docs


def create_document(access_token: str, *, title: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{DOCS_API}/documents",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"title": title},
        )
    if response.status_code >= 400:
        raise GoogleDocsAPIError(f"Docs API {response.status_code}", status_code=response.status_code)
    return response.json()


def batch_update_document(
    access_token: str,
    document_id: str,
    requests: list[dict[str, Any]],
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{DOCS_API}/documents/{document_id}:batchUpdate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"requests": requests},
        )
    if response.status_code >= 400:
        raise GoogleDocsAPIError(f"Docs API {response.status_code}", status_code=response.status_code)
    return response.json()


def replace_text(
    access_token: str,
    document_id: str,
    *,
    find_text: str,
    replace_text_value: str,
) -> dict[str, Any]:
    return batch_update_document(
        access_token,
        document_id,
        [
            {
                "replaceAllText": {
                    "containsText": {"text": find_text, "matchCase": True},
                    "replaceText": replace_text_value,
                }
            }
        ],
    )


def insert_table(
    access_token: str,
    document_id: str,
    *,
    rows: int,
    columns: int,
    index: int = 1,
) -> dict[str, Any]:
    return batch_update_document(
        access_token,
        document_id,
        [{"insertTable": {"rows": rows, "columns": columns, "location": {"index": index}}}],
    )


def export_pdf(access_token: str, document_id: str) -> bytes:
    from app.connectors.google_drive import export_file

    return export_file(access_token, document_id, mime_type="application/pdf")


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
