"""Confluence Cloud REST API v2 client (STA-44)."""
from __future__ import annotations

import re
import time
from html import unescape
from typing import Any

import httpx

from app.connectors.confluence_oauth import confluence_api_base_url

TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class ConfluenceAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def html_to_text(value: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _request(
    method: str,
    cloud_id: str,
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = confluence_api_base_url(cloud_id=cloud_id)
    url = f"{base}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, params=params)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise ConfluenceAPIError(
                    f"Confluence API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()
        except ConfluenceAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ConfluenceAPIError("Confluence API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ConfluenceAPIError(str(exc)) from exc
    raise ConfluenceAPIError(str(last_error or "Confluence API request failed"))


def _paginate(
    cloud_id: str,
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    results_key: str = "results",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    base_params = dict(params or {})
    while True:
        query = dict(base_params)
        if cursor:
            query["cursor"] = cursor
        data = _request("GET", cloud_id, access_token, path, params=query)
        batch = data.get(results_key) or []
        if isinstance(batch, list):
            items.extend(dict(item) for item in batch if isinstance(item, dict))
        links = data.get("_links") if isinstance(data.get("_links"), dict) else {}
        next_link = str(links.get("next") or "")
        if "cursor=" in next_link:
            cursor = next_link.split("cursor=", 1)[1].split("&", 1)[0]
            continue
        break
    return items


def normalize_space(space: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(space.get("id") or ""),
        "key": str(space.get("key") or ""),
        "name": str(space.get("name") or space.get("key") or ""),
        "type": str(space.get("type") or "space"),
    }


def list_spaces(access_token: str, cloud_id: str, *, limit: int = 250) -> list[dict[str, Any]]:
    spaces = _paginate(
        cloud_id,
        access_token,
        "/spaces",
        params={"limit": min(max(1, limit), 250)},
    )
    return [normalize_space(space) for space in spaces if space.get("id")]


def search_spaces(
    access_token: str,
    cloud_id: str,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    spaces = list_spaces(access_token, cloud_id, limit=250)
    if not query:
        return spaces[:limit]
    needle = query.strip().lower()
    filtered = [
        space
        for space in spaces
        if needle in str(space.get("name") or "").lower()
        or needle in str(space.get("key") or "").lower()
    ]
    return filtered[:limit]


def list_space_pages(
    access_token: str,
    cloud_id: str,
    space_id: str,
    *,
    limit: int = 250,
) -> list[dict[str, Any]]:
    pages = _paginate(
        cloud_id,
        access_token,
        f"/spaces/{space_id}/pages",
        params={"limit": min(max(1, limit), 250)},
    )
    normalized: list[dict[str, Any]] = []
    for page in pages:
        page_id = page.get("id")
        if not page_id:
            continue
        normalized.append(
            {
                "id": str(page_id),
                "title": str(page.get("title") or page_id),
                "status": str(page.get("status") or "current"),
                "space_id": str(space_id),
            }
        )
    return normalized


def get_page_view_text(access_token: str, cloud_id: str, page_id: str) -> tuple[str, str, str | None]:
    """Return (title, plain_text_body, version_created_at)."""
    data = _request(
        "GET",
        cloud_id,
        access_token,
        f"/pages/{page_id}",
        params={"body-format": "view"},
    )
    title = str(data.get("title") or page_id)
    body = data.get("body") if isinstance(data.get("body"), dict) else {}
    view = body.get("view") if isinstance(body.get("view"), dict) else {}
    raw_value = str(view.get("value") or "")
    text = html_to_text(raw_value)
    version = data.get("version") if isinstance(data.get("version"), dict) else {}
    created_at = version.get("createdAt")
    return title, text, str(created_at) if created_at else None
