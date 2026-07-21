"""Catalog executors for connected vendor file read/search (Phase 1)."""
from __future__ import annotations

from typing import Any

from app.connectors.connector_tool_auth import resolve_microsoft365_access_token, resolve_slack_bot_token
from app.connectors.confluence import ConfluenceAPIError, get_page_view_text
from app.connectors.confluence_oauth import ensure_confluence_session
from app.connectors.google_drive import GoogleDriveAPIError, get_file, search_files as drive_search_files
from app.connectors.microsoft365 import (
    Microsoft365APIError,
    download_drive_item_content,
    download_onedrive_item_content,
    get_drive_item,
    get_onedrive_item,
    search_drive_items,
    search_onedrive_items,
)
from app.connectors.notion import NotionAPIError, export_page_text, get_page, search as notion_search
from app.connectors.notion_oauth import ensure_notion_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.connectors.slack import download_file as slack_download_file, get_file_info, list_files as slack_list_files
from app.services.connected_files_service import (
    ConnectedFileError,
    build_file_citation_fields,
    chunk_connected_file_text,
    confluence_search_hits,
    extract_connected_file_text,
    fetch_google_drive_content,
    get_transient_file_content,
    google_drive_search_hits,
    microsoft_graph_search_hits,
    normalize_file_metadata,
    notion_search_hits,
    set_transient_file_content,
    slack_search_hits,
)
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolConnectorNotConnectedError,
    ToolContext,
    ToolValidationError,
)


def _connector_by_type(ctx: ToolContext, connector_type: str, params: dict[str, Any]) -> dict[str, Any]:
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, connector_type, environment_name=ctx.environment_name)
    if not conn:
        raise ToolConnectorNotConnectedError(f"No active {connector_type} connector found for org")
    return conn


def _handle_vendor_error(exc: Exception) -> Exception:
    if isinstance(exc, ConnectedFileError):
        return ToolValidationError(str(exc))
    if hasattr(exc, "status_code") and getattr(exc, "status_code") in {401, 403, 404}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _google_drive_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.google_vendor_oauth import ensure_google_vendor_session

    conn = _connector_by_type(ctx, "google_drive", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "google_drive", "google_drive", cid)
    token, err = ensure_google_vendor_session(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ToolAuthExpiredError(err or "Google Drive OAuth not connected")
    return cid, token


def _m365_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    conn = _connector_by_type(ctx, "microsoft365", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "microsoft365", "microsoft365", cid)
    token = resolve_microsoft365_access_token(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ToolAuthExpiredError("Microsoft 365 OAuth not connected")
    return cid, token


def _slack_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    conn = _connector_by_type(ctx, "slack", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "slack", "slack", cid)
    token = resolve_slack_bot_token(ctx.client, ctx.org_id, cid, ctx.settings)
    if not token:
        raise ToolAuthExpiredError("Slack OAuth not connected")
    return cid, token


def _notion_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    conn = _connector_by_type(ctx, "notion", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "notion", "notion", cid)
    token, err = ensure_notion_session(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ToolAuthExpiredError(err or "Notion OAuth not connected")
    return cid, token


def _confluence_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    conn = _connector_by_type(ctx, "confluence", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "confluence", "confluence", cid)
    token, cloud_id, err = ensure_confluence_session(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token or not cloud_id:
        raise ToolAuthExpiredError(err or "Confluence OAuth not connected")
    return cid, token, cloud_id


def _content_payload(
    *,
    org_id: str,
    vendor: str,
    file_id: str,
    filename: str,
    mime_type: str | None,
    data: bytes,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    cached = get_transient_file_content(org_id, vendor, file_id)
    if cached is not None:
        return cached
    text, extract_meta = extract_connected_file_text(data, filename=filename, mime_type=mime_type)
    chunks = chunk_connected_file_text(text, metadata={**metadata, **extract_meta})
    payload = {
        "file_id": file_id,
        "vendor": vendor,
        "metadata": metadata,
        "text": text,
        "text_length": len(text),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "citation": build_file_citation_fields(metadata),
        "storage": "transient_in_memory",
        "truncated": bool(extract_meta.get("truncated")),
    }
    set_transient_file_content(org_id, vendor, file_id, payload)
    return payload


def _exec_google_drive_search_files(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_drive_session(ctx, params)
    query = params.get("query") or params.get("q")
    if not query:
        raise ToolValidationError("google_drive.search_files requires query")
    try:
        raw = drive_search_files(
            token,
            query=str(query),
            scope=str(params["scope"]) if params.get("scope") else None,
            page_size=int(params.get("page_size") or params.get("limit") or 25),
        )
        hits = google_drive_search_hits(raw)
    except GoogleDriveAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="google_drive.search_files",
        connector_id=cid,
        data={"files": hits, "total": len(hits)},
    )


def _exec_google_drive_get_file_metadata(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_drive_session(ctx, params)
    file_id = params.get("file_id") or params.get("fileId")
    if not file_id:
        raise ToolValidationError("google_drive.get_file_metadata requires file_id")
    try:
        raw = get_file(token, str(file_id))
    except GoogleDriveAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    metadata = normalize_file_metadata(
        vendor="google_drive",
        file_id=str(raw.get("id") or file_id),
        name=str(raw.get("name") or file_id),
        mime_type=str(raw.get("mimeType") or "") or None,
        modified_at=str(raw.get("modifiedTime") or "") or None,
        web_link=str(raw.get("webViewLink") or raw.get("webContentLink") or "") or None,
        path=str(raw.get("name") or file_id),
        size=int(raw["size"]) if raw.get("size") is not None else None,
    )
    return NormalizedResult(
        success=True,
        action="google_drive.get_file_metadata",
        connector_id=cid,
        data={"file": metadata},
    )


def _exec_google_drive_get_file_content(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_drive_session(ctx, params)
    file_id = params.get("file_id") or params.get("fileId")
    if not file_id:
        raise ToolValidationError("google_drive.get_file_content requires file_id")
    try:
        meta_raw = get_file(token, str(file_id))
        metadata = normalize_file_metadata(
            vendor="google_drive",
            file_id=str(meta_raw.get("id") or file_id),
            name=str(meta_raw.get("name") or file_id),
            mime_type=str(meta_raw.get("mimeType") or "") or None,
            modified_at=str(meta_raw.get("modifiedTime") or "") or None,
            web_link=str(meta_raw.get("webViewLink") or "") or None,
            path=str(meta_raw.get("name") or file_id),
            size=int(meta_raw["size"]) if meta_raw.get("size") is not None else None,
        )
        data, filename = fetch_google_drive_content(token, str(file_id), mime_type=metadata.get("mime_type"))
    except (GoogleDriveAPIError, ConnectedFileError) as exc:
        raise _handle_vendor_error(exc) from exc
    payload = _content_payload(
        org_id=ctx.org_id,
        vendor="google_drive",
        file_id=str(file_id),
        filename=filename,
        mime_type=metadata.get("mime_type"),
        data=data,
        metadata=metadata,
    )
    return NormalizedResult(
        success=True,
        action="google_drive.get_file_content",
        connector_id=cid,
        data=payload,
    )


def _exec_m365_search_files(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    query = params.get("query") or params.get("q")
    if not query:
        raise ToolValidationError("microsoft365.search_files requires query")
    drive_id = params.get("drive_id")
    try:
        if drive_id:
            raw = search_drive_items(token, drive_id=str(drive_id), query=str(query))
        else:
            raw = search_onedrive_items(token, query=str(query))
        hits = microsoft_graph_search_hits(raw)
    except Microsoft365APIError as exc:
        raise _handle_vendor_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="microsoft365.search_files",
        connector_id=cid,
        data={"files": hits, "total": len(hits)},
    )


def _exec_m365_get_file_metadata(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    file_id = params.get("file_id") or params.get("item_id")
    drive_id = params.get("drive_id")
    if not file_id:
        raise ToolValidationError("microsoft365.get_file_metadata requires file_id")
    try:
        if drive_id:
            raw = get_drive_item(token, drive_id=str(drive_id), item_id=str(file_id))
        else:
            raw = get_onedrive_item(token, item_id=str(file_id))
    except Microsoft365APIError as exc:
        raise _handle_vendor_error(exc) from exc
    parent = raw.get("parentReference") if isinstance(raw.get("parentReference"), dict) else {}
    metadata = normalize_file_metadata(
        vendor="microsoft365",
        file_id=str(raw.get("id") or file_id),
        name=str(raw.get("name") or file_id),
        mime_type=str(raw.get("file", {}).get("mimeType") if isinstance(raw.get("file"), dict) else raw.get("mimeType") or "") or None,
        modified_at=str(raw.get("lastModifiedDateTime") or "") or None,
        web_link=str(raw.get("webUrl") or "") or None,
        path=str(parent.get("path") or raw.get("name") or file_id),
        size=int(raw["size"]) if raw.get("size") is not None else None,
        extra={"drive_id": parent.get("driveId") or drive_id},
    )
    return NormalizedResult(
        success=True,
        action="microsoft365.get_file_metadata",
        connector_id=cid,
        data={"file": metadata},
    )


def _exec_m365_get_file_content(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    file_id = params.get("file_id") or params.get("item_id")
    drive_id = params.get("drive_id")
    if not file_id:
        raise ToolValidationError("microsoft365.get_file_content requires file_id")
    try:
        if drive_id:
            raw = get_drive_item(token, drive_id=str(drive_id), item_id=str(file_id))
            data = download_drive_item_content(token, drive_id=str(drive_id), item_id=str(file_id))
        else:
            raw = get_onedrive_item(token, item_id=str(file_id))
            data = download_onedrive_item_content(token, item_id=str(file_id))
    except Microsoft365APIError as exc:
        raise _handle_vendor_error(exc) from exc
    parent = raw.get("parentReference") if isinstance(raw.get("parentReference"), dict) else {}
    metadata = normalize_file_metadata(
        vendor="microsoft365",
        file_id=str(raw.get("id") or file_id),
        name=str(raw.get("name") or file_id),
        mime_type=str(raw.get("file", {}).get("mimeType") if isinstance(raw.get("file"), dict) else raw.get("mimeType") or "") or None,
        modified_at=str(raw.get("lastModifiedDateTime") or "") or None,
        web_link=str(raw.get("webUrl") or "") or None,
        path=str(parent.get("path") or raw.get("name") or file_id),
        size=int(raw["size"]) if raw.get("size") is not None else None,
        extra={"drive_id": parent.get("driveId") or drive_id},
    )
    payload = _content_payload(
        org_id=ctx.org_id,
        vendor="microsoft365",
        file_id=str(file_id),
        filename=str(metadata["name"]),
        mime_type=metadata.get("mime_type"),
        data=data,
        metadata=metadata,
    )
    return NormalizedResult(
        success=True,
        action="microsoft365.get_file_content",
        connector_id=cid,
        data=payload,
    )


def _exec_slack_search_files(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_session(ctx, params)
    query = params.get("query") or params.get("q")
    try:
        raw = slack_list_files(
            token,
            query=str(query) if query else None,
            channel=str(params["channel"]) if params.get("channel") else None,
            count=int(params.get("count") or params.get("limit") or 20),
        )
        hits = slack_search_hits(raw)
    except ValueError as exc:
        raise _handle_vendor_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="slack.search_files",
        connector_id=cid,
        data={"files": hits, "total": len(hits)},
    )


def _exec_slack_get_file_metadata(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_session(ctx, params)
    file_id = params.get("file_id")
    if not file_id:
        raise ToolValidationError("slack.get_file_metadata requires file_id")
    try:
        raw = get_file_info(token, str(file_id))
        row = raw.get("file") if isinstance(raw.get("file"), dict) else {}
    except ValueError as exc:
        raise _handle_vendor_error(exc) from exc
    metadata = normalize_file_metadata(
        vendor="slack",
        file_id=str(row.get("id") or file_id),
        name=str(row.get("name") or row.get("title") or file_id),
        mime_type=str(row.get("mimetype") or "") or None,
        modified_at=str(row.get("timestamp") or "") or None,
        web_link=str(row.get("permalink") or "") or None,
        path=str(row.get("name") or file_id),
        size=int(row["size"]) if row.get("size") is not None else None,
    )
    return NormalizedResult(
        success=True,
        action="slack.get_file_metadata",
        connector_id=cid,
        data={"file": metadata},
    )


def _exec_slack_get_file_content(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_session(ctx, params)
    file_id = params.get("file_id")
    if not file_id:
        raise ToolValidationError("slack.get_file_content requires file_id")
    try:
        meta_raw = get_file_info(token, str(file_id))
        row = meta_raw.get("file") if isinstance(meta_raw.get("file"), dict) else {}
        data, filename = slack_download_file(token, str(file_id))
    except ValueError as exc:
        raise _handle_vendor_error(exc) from exc
    metadata = normalize_file_metadata(
        vendor="slack",
        file_id=str(row.get("id") or file_id),
        name=str(filename or row.get("name") or file_id),
        mime_type=str(row.get("mimetype") or "") or None,
        modified_at=str(row.get("timestamp") or "") or None,
        web_link=str(row.get("permalink") or "") or None,
        path=str(filename or row.get("name") or file_id),
        size=int(row["size"]) if row.get("size") is not None else None,
    )
    payload = _content_payload(
        org_id=ctx.org_id,
        vendor="slack",
        file_id=str(file_id),
        filename=str(metadata["name"]),
        mime_type=metadata.get("mime_type"),
        data=data,
        metadata=metadata,
    )
    return NormalizedResult(
        success=True,
        action="slack.get_file_content",
        connector_id=cid,
        data=payload,
    )


def _exec_notion_search_files(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _notion_session(ctx, params)
    query = params.get("query") or params.get("q") or ""
    try:
        raw = notion_search(token, query=str(query) if query else None, filter_object="page")
        hits = notion_search_hits(raw)
    except NotionAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="notion.search_files",
        connector_id=cid,
        data={"files": hits, "total": len(hits)},
    )


def _exec_notion_get_file_metadata(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _notion_session(ctx, params)
    file_id = params.get("file_id") or params.get("page_id")
    if not file_id:
        raise ToolValidationError("notion.get_file_metadata requires file_id")
    try:
        raw = get_page(token, str(file_id))
    except NotionAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    from app.connectors.notion import page_title

    title = page_title(raw)
    metadata = normalize_file_metadata(
        vendor="notion",
        file_id=str(raw.get("id") or file_id),
        name=title,
        modified_at=str(raw.get("last_edited_time") or "") or None,
        web_link=str(raw.get("url") or "") or None,
        path=f"Notion / {title}",
        extra={"page_id": str(file_id)},
    )
    return NormalizedResult(
        success=True,
        action="notion.get_file_metadata",
        connector_id=cid,
        data={"file": metadata},
    )


def _exec_notion_get_file_content(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _notion_session(ctx, params)
    file_id = params.get("file_id") or params.get("page_id")
    if not file_id:
        raise ToolValidationError("notion.get_file_content requires file_id")
    try:
        title, body, edited = export_page_text(token, str(file_id))
    except NotionAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    metadata = normalize_file_metadata(
        vendor="notion",
        file_id=str(file_id),
        name=title,
        modified_at=edited,
        path=f"Notion / {title}",
        extra={"page_id": str(file_id)},
    )
    chunks = chunk_connected_file_text(body, metadata=metadata)
    payload = {
        "file_id": str(file_id),
        "vendor": "notion",
        "metadata": metadata,
        "text": body,
        "text_length": len(body),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "citation": build_file_citation_fields(metadata),
        "storage": "transient_in_memory",
        "truncated": False,
    }
    return NormalizedResult(
        success=True,
        action="notion.get_file_content",
        connector_id=cid,
        data=payload,
    )


def _exec_confluence_search_files(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _confluence_session(ctx, params)
    query = params.get("query") or params.get("q")
    if not query:
        raise ToolValidationError("confluence.search_files requires query")
    from app.connectors.confluence import search_pages

    try:
        raw = search_pages(token, cloud_id, query=str(query))
        hits = confluence_search_hits(raw)
    except ConfluenceAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="confluence.search_files",
        connector_id=cid,
        data={"files": hits, "total": len(hits)},
    )


def _exec_confluence_get_file_metadata(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _confluence_session(ctx, params)
    file_id = params.get("file_id") or params.get("page_id")
    if not file_id:
        raise ToolValidationError("confluence.get_file_metadata requires file_id")
    from app.connectors.confluence import get_page

    try:
        raw = get_page(token, cloud_id, str(file_id))
    except ConfluenceAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    links = raw.get("_links") if isinstance(raw.get("_links"), dict) else {}
    title = str(raw.get("title") or file_id)
    metadata = normalize_file_metadata(
        vendor="confluence",
        file_id=str(raw.get("id") or file_id),
        name=title,
        modified_at=str(raw.get("version", {}).get("createdAt") or "") if isinstance(raw.get("version"), dict) else None,
        web_link=str(links.get("webui") or "") or None,
        path=f"Confluence / {title}",
        extra={"page_id": str(file_id), "cloud_id": cloud_id},
    )
    return NormalizedResult(
        success=True,
        action="confluence.get_file_metadata",
        connector_id=cid,
        data={"file": metadata},
    )


def _exec_confluence_get_file_content(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _confluence_session(ctx, params)
    file_id = params.get("file_id") or params.get("page_id")
    if not file_id:
        raise ToolValidationError("confluence.get_file_content requires file_id")
    try:
        title, body, edited = get_page_view_text(token, cloud_id, str(file_id))
    except ConfluenceAPIError as exc:
        raise _handle_vendor_error(exc) from exc
    metadata = normalize_file_metadata(
        vendor="confluence",
        file_id=str(file_id),
        name=title,
        modified_at=edited,
        path=f"Confluence / {title}",
        extra={"page_id": str(file_id), "cloud_id": cloud_id},
    )
    chunks = chunk_connected_file_text(body, metadata=metadata)
    payload = {
        "file_id": str(file_id),
        "vendor": "confluence",
        "metadata": metadata,
        "text": body,
        "text_length": len(body),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "citation": build_file_citation_fields(metadata),
        "storage": "transient_in_memory",
        "truncated": False,
    }
    return NormalizedResult(
        success=True,
        action="confluence.get_file_content",
        connector_id=cid,
        data=payload,
    )


def _alias(action: str, fn: Any) -> dict[str, Any]:
    vendor, _, rest = action.partition(".")
    from app.connectors.action_catalog.tool_aliases import REGISTRY_VENDOR_PREFIX_ALIASES

    keys = {action}
    alias = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
    if alias and rest:
        keys.add(f"{alias}.{rest}")
    return {key: fn for key in keys}


_CONNECTED_FILE_TOOLS: dict[str, Any] = {}
for catalog_action, fn in [
    ("google_drive.search_files", _exec_google_drive_search_files),
    ("google_drive.get_file_metadata", _exec_google_drive_get_file_metadata),
    ("google_drive.get_file_content", _exec_google_drive_get_file_content),
    ("microsoft365.search_files", _exec_m365_search_files),
    ("microsoft365.get_file_metadata", _exec_m365_get_file_metadata),
    ("microsoft365.get_file_content", _exec_m365_get_file_content),
    ("slack.search_files", _exec_slack_search_files),
    ("slack.get_file_metadata", _exec_slack_get_file_metadata),
    ("slack.get_file_content", _exec_slack_get_file_content),
    ("notion.search_files", _exec_notion_search_files),
    ("notion.get_file_metadata", _exec_notion_get_file_metadata),
    ("notion.get_file_content", _exec_notion_get_file_content),
    ("confluence.search_files", _exec_confluence_search_files),
    ("confluence.get_file_metadata", _exec_confluence_get_file_metadata),
    ("confluence.get_file_content", _exec_confluence_get_file_content),
]:
    _CONNECTED_FILE_TOOLS.update(_alias(catalog_action, fn))

CONNECTED_FILE_TOOLS: dict[str, Any] = _CONNECTED_FILE_TOOLS
