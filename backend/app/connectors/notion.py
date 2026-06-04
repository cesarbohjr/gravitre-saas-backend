"""Notion API client for search and page export (STA-43)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TIMEOUT_SEC = 30.0

logger = logging.getLogger(__name__)


class NotionAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def api_request(
    method: str,
    path: str,
    access_token: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{NOTION_API_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(
            method,
            url,
            headers=_headers(access_token),
            json=json_body,
            params=params,
        )
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise NotionAPIError(
            f"Notion API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    data = response.json()
    return data if isinstance(data, dict) else {"data": data}


def search(
    access_token: str,
    *,
    query: str | None = None,
    filter_object: str | None = None,
    page_size: int = 20,
) -> dict[str, Any]:
    body: dict[str, Any] = {"page_size": max(1, min(int(page_size), 100))}
    if query:
        body["query"] = query
    if filter_object in {"page", "database"}:
        body["filter"] = {"property": "object", "value": filter_object}
    return api_request("POST", "/search", access_token, json_body=body)


def get_page(access_token: str, page_id: str) -> dict[str, Any]:
    return api_request("GET", f"/pages/{page_id}", access_token)


def query_database(
    access_token: str,
    database_id: str,
    *,
    page_size: int = 100,
    start_cursor: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"page_size": max(1, min(int(page_size), 100))}
    if start_cursor:
        body["start_cursor"] = start_cursor
    return api_request("POST", f"/databases/{database_id}/query", access_token, json_body=body)


def list_block_children(
    access_token: str,
    block_id: str,
    *,
    start_cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page_size": 100}
    if start_cursor:
        params["start_cursor"] = start_cursor
    return api_request("GET", f"/blocks/{block_id}/children", access_token, params=params)


def _rich_text_plain(rich_text: list[Any]) -> str:
    parts: list[str] = []
    for item in rich_text or []:
        if isinstance(item, dict):
            parts.append(str(item.get("plain_text") or ""))
    return "".join(parts).strip()


def block_to_lines(block: dict[str, Any]) -> list[str]:
    block_type = block.get("type")
    if not isinstance(block_type, str):
        return []
    payload = block.get(block_type)
    if not isinstance(payload, dict):
        return []
    rich = payload.get("rich_text")
    text = _rich_text_plain(rich) if isinstance(rich, list) else ""

    if block_type == "heading_1":
        return [f"# {text}"] if text else []
    if block_type == "heading_2":
        return [f"## {text}"] if text else []
    if block_type == "heading_3":
        return [f"### {text}"] if text else []
    if block_type in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph", "quote", "callout"}:
        prefix = "- " if block_type == "bulleted_list_item" else ""
        if block_type == "to_do" and payload.get("checked"):
            prefix = "[x] "
        elif block_type == "to_do":
            prefix = "[ ] "
        return [f"{prefix}{text}".strip()] if text or block_type == "to_do" else []
    if block_type == "code":
        lang = payload.get("language") or ""
        return [f"```{lang}\n{text}\n```"] if text else []
    if block_type == "divider":
        return ["---"]
    return [text] if text else []


def fetch_block_tree_text(
    access_token: str,
    block_id: str,
    *,
    depth: int = 0,
    max_depth: int = 8,
) -> str:
    if depth > max_depth:
        return ""
    lines: list[str] = []
    cursor: str | None = None
    while True:
        data = list_block_children(access_token, block_id, start_cursor=cursor)
        for block in data.get("results") or []:
            if not isinstance(block, dict):
                continue
            lines.extend(block_to_lines(block))
            if block.get("has_children"):
                child_id = str(block.get("id") or "")
                if child_id:
                    nested = fetch_block_tree_text(
                        access_token,
                        child_id,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    if nested.strip():
                        lines.append(nested)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return "\n".join(line for line in lines if line).strip()


def page_title(page: dict[str, Any]) -> str:
    props = page.get("properties") if isinstance(page.get("properties"), dict) else {}
    for prop in props.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "title":
            title_items = prop.get("title")
            if isinstance(title_items, list):
                return _rich_text_plain(title_items) or "Untitled"
    return "Untitled"


def export_page_text(access_token: str, page_id: str) -> tuple[str, str, str | None]:
    """Return (title, body_text, last_edited_time)."""
    page = get_page(access_token, page_id)
    title = page_title(page)
    body = fetch_block_tree_text(access_token, page_id)
    edited = page.get("last_edited_time")
    return title, body, str(edited) if edited else None


def collect_database_page_ids(access_token: str, database_id: str) -> list[str]:
    ids: list[str] = []
    cursor: str | None = None
    while True:
        data = query_database(access_token, database_id, start_cursor=cursor)
        for row in data.get("results") or []:
            if isinstance(row, dict) and row.get("object") == "page" and row.get("id"):
                ids.append(str(row["id"]))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return ids


def normalize_search_result(item: dict[str, Any]) -> dict[str, Any]:
    obj = str(item.get("object") or "")
    item_id = str(item.get("id") or "")
    title = page_title(item) if obj == "page" else ""
    if obj == "database" and isinstance(item.get("title"), list):
        title = _rich_text_plain(item.get("title")) or "Database"
    return {
        "id": item_id,
        "type": obj,
        "title": title or item_id,
        "url": item.get("url"),
        "last_edited_time": item.get("last_edited_time"),
    }
