"""Live folder browsing for connected-file picker (read-only, permission-checked at vendor)."""
from __future__ import annotations

from typing import Any

from app.connectors.confluence import ConfluenceAPIError, search_pages as confluence_search_pages
from app.connectors.confluence_oauth import ensure_confluence_session
from app.connectors.google_drive import GoogleDriveAPIError, list_files as drive_list_files
from app.connectors.google_vendor_oauth import ensure_google_vendor_session
from app.connectors.microsoft365 import Microsoft365APIError, list_onedrive_items
from app.connectors.notion import NotionAPIError, search as notion_search
from app.connectors.notion_oauth import ensure_notion_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.constants import ACTIVE_CONNECTOR_STATUSES
from app.connectors.repository import get_connector_by_type, list_connectors
from app.connectors.slack import list_files as slack_list_files
from app.connectors.connector_tool_auth import resolve_microsoft365_access_token, resolve_slack_bot_token
from app.services.connected_files_service import (
    confluence_search_hits,
    normalize_file_metadata,
    notion_search_hits,
    slack_search_hits,
)
from app.services.tool_types import ToolContext

GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
M365_FOLDER_MIME = "application/vnd.ms-folder"

FILE_BROWSE_VENDOR_KEYS: frozenset[str] = frozenset(
    {"google_drive", "microsoft365", "slack", "notion", "confluence"}
)

_VENDOR_LABELS = {
    "google_drive": "Google Drive",
    "microsoft365": "Microsoft 365 / OneDrive",
    "slack": "Slack files",
    "notion": "Notion",
    "confluence": "Confluence",
}


def _browse_entry(
    *,
    vendor: str,
    connector_id: str,
    entry_id: str,
    name: str,
    kind: str,
    mime_type: str | None = None,
    modified_at: str | None = None,
    web_link: str | None = None,
    path: str | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    return {
        "vendor": vendor,
        "connector_id": connector_id,
        "id": entry_id,
        "name": name,
        "kind": kind,
        "mime_type": mime_type,
        "modified_at": modified_at,
        "web_link": web_link,
        "path": path or name,
        "size": size,
    }


def list_connected_file_vendors(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> list[dict[str, Any]]:
    rows = list_connectors(client, org_id, environment_name=environment_name) or []
    usable = {str(s).lower() for s in ACTIVE_CONNECTOR_STATUSES}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vendor = str(row.get("type") or row.get("vendor") or row.get("connector_type") or "").strip().lower()
        if vendor not in FILE_BROWSE_VENDOR_KEYS or vendor in seen:
            continue
        status = str(row.get("status") or "active").lower()
        if status not in usable:
            continue
        seen.add(vendor)
        out.append(
            {
                "vendor": vendor,
                "label": _VENDOR_LABELS.get(vendor, vendor),
                "connector_id": str(row.get("id") or ""),
                "connector_name": str(row.get("name") or _VENDOR_LABELS.get(vendor, vendor)),
            }
        )
    return sorted(out, key=lambda item: item.get("label") or "")


def browse_connected_files(
    ctx: ToolContext,
    *,
    vendor: str,
    connector_id: str | None = None,
    folder_id: str | None = None,
    search: str | None = None,
    page_size: int = 40,
) -> dict[str, Any]:
    vendor_key = (vendor or "").strip().lower()
    if vendor_key not in FILE_BROWSE_VENDOR_KEYS:
        raise ValueError(f"Unsupported browse vendor: {vendor}")

    conn = None
    if connector_id:
        from app.connectors.repository import get_connector

        conn = get_connector(ctx.client, ctx.org_id, connector_id, environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, vendor_key, environment_name=ctx.environment_name)
    if not conn:
        raise ValueError(f"No active {vendor_key} connector for this organization")

    cid = str(conn["id"])
    limit = min(max(int(page_size or 40), 1), 100)
    query_filter = (search or "").strip()

    if vendor_key == "google_drive":
        return _browse_google_drive(ctx, cid, folder_id=folder_id, search=query_filter, limit=limit)
    if vendor_key == "microsoft365":
        return _browse_m365_onedrive(ctx, cid, folder_id=folder_id, search=query_filter, limit=limit)
    if vendor_key == "slack":
        return _browse_slack(ctx, cid, search=query_filter, limit=limit)
    if vendor_key == "notion":
        return _browse_notion(ctx, cid, search=query_filter, limit=limit)
    if vendor_key == "confluence":
        return _browse_confluence(ctx, cid, search=query_filter, limit=limit)
    raise ValueError(f"Browse not implemented for {vendor_key}")


def _browse_google_drive(
    ctx: ToolContext,
    connector_id: str,
    *,
    folder_id: str | None,
    search: str,
    limit: int,
) -> dict[str, Any]:
    enforce_rate_limit(ctx.client, ctx.org_id, "google_drive", "google_drive", connector_id)
    token, err = ensure_google_vendor_session(
        ctx.client, ctx.org_id, connector_id, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ValueError(err or "Google Drive OAuth not connected")

    parent = (folder_id or "root").strip() or "root"
    clauses = [f"'{parent}' in parents", "trashed = false"]
    if search:
        safe = search.replace("'", "\\'")
        clauses.append(f"name contains '{safe}'")
    q = " and ".join(clauses)
    try:
        raw = drive_list_files(token, page_size=limit, query=q)
    except GoogleDriveAPIError as exc:
        raise ValueError(str(exc)) from exc

    entries: list[dict[str, Any]] = []
    for row in raw.get("files") or []:
        if not isinstance(row, dict):
            continue
        mime = str(row.get("mimeType") or "")
        is_folder = mime == GOOGLE_FOLDER_MIME
        meta = normalize_file_metadata(
            vendor="google_drive",
            file_id=str(row.get("id") or ""),
            name=str(row.get("name") or "Untitled"),
            mime_type=mime or None,
            modified_at=str(row.get("modifiedTime") or "") or None,
            web_link=str(row.get("webViewLink") or "") or None,
            path=str(row.get("name") or ""),
            size=int(row["size"]) if row.get("size") is not None else None,
        )
        entries.append(
            _browse_entry(
                vendor="google_drive",
                connector_id=connector_id,
                entry_id=meta["file_id"],
                name=meta["name"],
                kind="folder" if is_folder else "file",
                mime_type=meta.get("mime_type"),
                modified_at=meta.get("modified_at"),
                web_link=meta.get("web_link"),
                path=meta.get("path"),
                size=meta.get("size"),
            )
        )
    entries.sort(key=lambda item: (0 if item["kind"] == "folder" else 1, (item.get("name") or "").lower()))
    return {
        "vendor": "google_drive",
        "connector_id": connector_id,
        "folder_id": parent,
        "entries": entries,
        "storage_note": "read_only_no_upload",
    }


def _browse_m365_onedrive(
    ctx: ToolContext,
    connector_id: str,
    *,
    folder_id: str | None,
    search: str,
    limit: int,
) -> dict[str, Any]:
    enforce_rate_limit(ctx.client, ctx.org_id, "microsoft365", "microsoft365", connector_id)
    token = resolve_microsoft365_access_token(
        ctx.client, ctx.org_id, connector_id, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ValueError("Microsoft 365 OAuth not connected")
    try:
        raw = list_onedrive_items(token, item_id=folder_id or None, top=limit)
    except Microsoft365APIError as exc:
        raise ValueError(str(exc)) from exc

    entries: list[dict[str, Any]] = []
    for row in raw.get("value") or []:
        if not isinstance(row, dict):
            continue
        if search and search.lower() not in str(row.get("name") or "").lower():
            continue
        is_folder = bool(row.get("folder"))
        mime = M365_FOLDER_MIME if is_folder else str((row.get("file") or {}).get("mimeType") or "")
        entry_id = str(row.get("id") or "")
        meta = normalize_file_metadata(
            vendor="microsoft365",
            file_id=entry_id,
            name=str(row.get("name") or "Untitled"),
            mime_type=mime or None,
            modified_at=str(row.get("lastModifiedDateTime") or "") or None,
            web_link=str(row.get("webUrl") or "") or None,
            path=str(row.get("name") or ""),
            size=int(row.get("size")) if row.get("size") is not None else None,
        )
        entries.append(
            _browse_entry(
                vendor="microsoft365",
                connector_id=connector_id,
                entry_id=meta["file_id"],
                name=meta["name"],
                kind="folder" if is_folder else "file",
                mime_type=meta.get("mime_type"),
                modified_at=meta.get("modified_at"),
                web_link=meta.get("web_link"),
                path=meta.get("path"),
                size=meta.get("size"),
            )
        )
    entries.sort(key=lambda item: (0 if item["kind"] == "folder" else 1, (item.get("name") or "").lower()))
    return {
        "vendor": "microsoft365",
        "connector_id": connector_id,
        "folder_id": folder_id or "root",
        "entries": entries,
        "storage_note": "read_only_no_upload",
    }


def _browse_slack(
    ctx: ToolContext,
    connector_id: str,
    *,
    search: str,
    limit: int,
) -> dict[str, Any]:
    enforce_rate_limit(ctx.client, ctx.org_id, "slack", "slack", connector_id)
    token = resolve_slack_bot_token(ctx.client, ctx.org_id, connector_id, ctx.settings)
    if not token:
        raise ValueError("Slack OAuth not connected")
    raw = slack_list_files(token, query=search or None, count=limit)
    hits = slack_search_hits(raw)
    entries = [
        _browse_entry(
            vendor="slack",
            connector_id=connector_id,
            entry_id=str(hit.get("file_id") or ""),
            name=str(hit.get("name") or "File"),
            kind="file",
            mime_type=hit.get("mime_type"),
            modified_at=hit.get("modified_at"),
            web_link=hit.get("web_link"),
            path=hit.get("path"),
            size=hit.get("size"),
        )
        for hit in hits
        if hit.get("file_id")
    ]
    return {
        "vendor": "slack",
        "connector_id": connector_id,
        "folder_id": None,
        "entries": entries,
        "storage_note": "read_only_no_upload",
        "browse_mode": "flat_files",
    }


def _browse_notion(
    ctx: ToolContext,
    connector_id: str,
    *,
    search: str,
    limit: int,
) -> dict[str, Any]:
    enforce_rate_limit(ctx.client, ctx.org_id, "notion", "notion", connector_id)
    token, err = ensure_notion_session(
        ctx.client, ctx.org_id, connector_id, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ValueError(err or "Notion OAuth not connected")
    try:
        raw = notion_search(token, query=search or "", page_size=limit)
    except NotionAPIError as exc:
        raise ValueError(str(exc)) from exc
    hits = notion_search_hits(raw)
    entries = [
        _browse_entry(
            vendor="notion",
            connector_id=connector_id,
            entry_id=str(hit.get("file_id") or ""),
            name=str(hit.get("name") or "Page"),
            kind="file",
            mime_type=hit.get("mime_type"),
            modified_at=hit.get("modified_at"),
            web_link=hit.get("web_link"),
            path=hit.get("path"),
        )
        for hit in hits
        if hit.get("file_id")
    ]
    return {
        "vendor": "notion",
        "connector_id": connector_id,
        "folder_id": None,
        "entries": entries,
        "storage_note": "read_only_no_upload",
        "browse_mode": "workspace_pages",
    }


def _browse_confluence(
    ctx: ToolContext,
    connector_id: str,
    *,
    search: str,
    limit: int,
) -> dict[str, Any]:
    enforce_rate_limit(ctx.client, ctx.org_id, "confluence", "confluence", connector_id)
    token, cloud_id, err = ensure_confluence_session(
        ctx.client, ctx.org_id, connector_id, ctx.settings, environment_name=ctx.environment_name
    )
    if not token or not cloud_id:
        raise ValueError(err or "Confluence OAuth not connected")
    from app.connectors.confluence import list_space_pages, list_spaces

    try:
        if search:
            raw = confluence_search_pages(token, cloud_id, query=search, limit=limit)
        else:
            results: list[dict[str, Any]] = []
            for space in list_spaces(token, cloud_id, limit=25):
                space_id = str(space.get("id") or "")
                if not space_id:
                    continue
                for page in list_space_pages(token, cloud_id, space_id, limit=50):
                    title = str(page.get("title") or "Untitled")
                    results.append(
                        {
                            **page,
                            "_links": {
                                "webui": f"/spaces/{space.get('key')}/pages/{page.get('id')}",
                            },
                        }
                    )
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            raw = {"results": results}
    except ConfluenceAPIError as exc:
        raise ValueError(str(exc)) from exc
    hits = confluence_search_hits(raw)
    entries = [
        _browse_entry(
            vendor="confluence",
            connector_id=connector_id,
            entry_id=str(hit.get("file_id") or ""),
            name=str(hit.get("name") or "Page"),
            kind="file",
            mime_type=hit.get("mime_type"),
            modified_at=hit.get("modified_at"),
            web_link=hit.get("web_link"),
            path=hit.get("path"),
        )
        for hit in hits
        if hit.get("file_id")
    ]
    return {
        "vendor": "confluence",
        "connector_id": connector_id,
        "folder_id": None,
        "entries": entries,
        "storage_note": "read_only_no_upload",
        "browse_mode": "wiki_pages",
    }
