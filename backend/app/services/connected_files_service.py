"""Read-only connected vendor file search/content (no Gravitre-side storage).

Fetched content is held in-memory only for the duration of a query/response cycle,
with an optional short-lived process-local cache for repeated reads within one turn.
Permission checks always hit the vendor API — never a cached permission snapshot.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.tool_types import ToolContext

from app.core.logging import get_logger
from app.rag.file_extract import UnsupportedFileTypeError, extract_text_from_bytes
from app.rag.ingest import chunk_document_text

logger = get_logger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CONTENT_CHARS = 500_000
_TRANSIENT_TTL_SECONDS = 60
_TRANSIENT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_GOOGLE_NATIVE_EXPORT = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class ConnectedFileError(Exception):
    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or "connected_file_error"


class ConnectedFileTooLargeError(ConnectedFileError):
    def __init__(self, size: int, limit: int = MAX_FILE_BYTES) -> None:
        super().__init__(
            f"File is {size:,} bytes; maximum supported size is {limit:,} bytes. "
            "Try a smaller export or ask about a specific section.",
            code="file_too_large",
        )


class ConnectedFileUnsupportedTypeError(ConnectedFileError):
    def __init__(self, mime_type: str | None, filename: str | None = None) -> None:
        label = filename or mime_type or "unknown type"
        super().__init__(
            f"Cannot read content for {label}. Supported types include PDF, DOCX, XLSX/CSV, "
            "plain text/markdown, and native Google Docs/Sheets exports.",
            code="unsupported_file_type",
        )


def is_permission_sensitive_file_action(invoke_action: str) -> bool:
    action = str(invoke_action or "").strip().lower()
    markers = (
        "search_files",
        "get_file_content",
        "files.content",
        "files.search",
    )
    return any(marker in action for marker in markers)


def normalize_file_metadata(
    *,
    vendor: str,
    file_id: str,
    name: str,
    mime_type: str | None = None,
    modified_at: str | None = None,
    web_link: str | None = None,
    path: str | None = None,
    size: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "vendor": vendor,
        "file_id": file_id,
        "name": name,
        "mime_type": mime_type,
        "modified_at": modified_at,
        "web_link": web_link,
        "path": path or name,
        "size": size,
    }
    if extra:
        payload.update(extra)
    return payload


def normalize_search_hit(row: dict[str, Any], *, vendor: str) -> dict[str, Any]:
    file_id = str(row.get("file_id") or row.get("id") or row.get("item_id") or "").strip()
    name = str(row.get("name") or row.get("title") or "Untitled").strip()
    parent_ref = row.get("parentReference") if isinstance(row.get("parentReference"), dict) else {}
    return normalize_file_metadata(
        vendor=vendor,
        file_id=file_id,
        name=name,
        mime_type=row.get("mime_type") or row.get("mimeType"),
        modified_at=row.get("modified_at") or row.get("modifiedTime") or row.get("lastModifiedDateTime"),
        web_link=row.get("web_link") or row.get("webViewLink") or row.get("webUrl"),
        path=row.get("path") or parent_ref.get("path") or name,
        size=int(row["size"]) if row.get("size") is not None else None,
        extra={k: v for k, v in row.items() if k.startswith("drive_") or k in {"page_id", "space_id"}},
    )


def _cache_key(org_id: str, vendor: str, file_id: str) -> str:
    return f"{org_id}:{vendor}:{file_id}"


def get_transient_file_content(org_id: str, vendor: str, file_id: str) -> dict[str, Any] | None:
    key = _cache_key(org_id, vendor, file_id)
    row = _TRANSIENT_CACHE.get(key)
    if not row:
        return None
    expires_at, payload = row
    if time.time() > expires_at:
        _TRANSIENT_CACHE.pop(key, None)
        return None
    return dict(payload)


def set_transient_file_content(
    org_id: str,
    vendor: str,
    file_id: str,
    payload: dict[str, Any],
) -> None:
    key = _cache_key(org_id, vendor, file_id)
    _TRANSIENT_CACHE[key] = (time.time() + _TRANSIENT_TTL_SECONDS, dict(payload))


def clear_transient_file_content_cache() -> None:
    _TRANSIENT_CACHE.clear()


def extract_connected_file_text(
    data: bytes,
    *,
    filename: str,
    mime_type: str | None = None,
    partial: bool = False,
) -> tuple[str, dict[str, Any]]:
    if len(data) > MAX_FILE_BYTES:
        if partial:
            data = data[:MAX_FILE_BYTES]
        else:
            raise ConnectedFileTooLargeError(len(data))
    try:
        text = extract_text_from_bytes(data, filename=filename, content_type=mime_type)
    except UnsupportedFileTypeError as exc:
        raise ConnectedFileUnsupportedTypeError(mime_type, filename) from exc
    except ValueError as exc:
        raise ConnectedFileError(str(exc), code="extract_failed") from exc
    truncated = False
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS]
        truncated = True
    meta = {"original_filename": filename, "content_type": mime_type, "truncated": truncated}
    return text, meta


def chunk_connected_file_text(
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    chunks = chunk_document_text(text)
    rows: list[dict[str, Any]] = []
    for index, content in enumerate(chunks):
        chunk_meta = dict(metadata or {})
        chunk_meta["chunk_index"] = index
        rows.append({"content": content, "metadata": chunk_meta, "chunk_index": index})
    return rows


def build_file_citation_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_path": metadata.get("path") or metadata.get("original_filename"),
        "file_name": metadata.get("name") or metadata.get("original_filename"),
        "web_link": metadata.get("web_link") or metadata.get("url"),
        "page": metadata.get("page"),
        "section": metadata.get("section"),
        "vendor": metadata.get("vendor"),
        "file_id": metadata.get("file_id"),
    }


def google_drive_search_hits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in raw.get("files") or []:
        if not isinstance(row, dict):
            continue
        hits.append(
            normalize_search_hit(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "mimeType": row.get("mimeType"),
                    "modifiedTime": row.get("modifiedTime"),
                    "webViewLink": row.get("webViewLink"),
                    "size": row.get("size"),
                },
                vendor="google_drive",
            )
        )
    return hits


def microsoft_graph_search_hits(raw: dict[str, Any], *, vendor: str = "microsoft365") -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in raw.get("value") or []:
        if not isinstance(row, dict):
            continue
        parent = row.get("parentReference") if isinstance(row.get("parentReference"), dict) else {}
        hits.append(
            normalize_search_hit(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "mimeType": row.get("file", {}).get("mimeType") if isinstance(row.get("file"), dict) else row.get("mimeType"),
                    "lastModifiedDateTime": row.get("lastModifiedDateTime"),
                    "webUrl": row.get("webUrl"),
                    "size": row.get("size"),
                    "path": parent.get("path"),
                    "drive_id": parent.get("driveId") or row.get("parentReference", {}).get("driveId"),
                },
                vendor=vendor,
            )
        )
    return hits


def slack_search_hits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in raw.get("files") or []:
        if not isinstance(row, dict):
            continue
        hits.append(
            normalize_search_hit(
                {
                    "id": row.get("id"),
                    "name": row.get("name") or row.get("title"),
                    "mimeType": row.get("mimetype"),
                    "modifiedTime": row.get("timestamp"),
                    "web_link": row.get("permalink"),
                    "size": row.get("size"),
                },
                vendor="slack",
            )
        )
    return hits


def notion_search_hits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in raw.get("results") or []:
        if not isinstance(row, dict) or row.get("object") != "page":
            continue
        page_id = str(row.get("id") or "")
        title = "Untitled"
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_items = prop.get("title")
                if isinstance(title_items, list) and title_items:
                    title = str(title_items[0].get("plain_text") or "Untitled")
        hits.append(
            normalize_file_metadata(
                vendor="notion",
                file_id=page_id,
                name=title,
                modified_at=str(row.get("last_edited_time") or "") or None,
                web_link=str(row.get("url") or "") or None,
                path=f"Notion / {title}",
                extra={"page_id": page_id},
            )
        )
    return hits


def confluence_search_hits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in raw.get("results") or raw.get("pages") or []:
        if not isinstance(row, dict):
            continue
        page_id = str(row.get("id") or "")
        title = str(row.get("title") or "Untitled")
        links = row.get("_links") if isinstance(row.get("_links"), dict) else {}
        web_link = str(links.get("webui") or links.get("base") or "") or None
        hits.append(
            normalize_file_metadata(
                vendor="confluence",
                file_id=page_id,
                name=title,
                modified_at=str(row.get("version", {}).get("createdAt") or "") if isinstance(row.get("version"), dict) else None,
                web_link=web_link,
                path=f"Confluence / {title}",
                extra={"page_id": page_id},
            )
        )
    return hits


def fetch_google_drive_content(access_token: str, file_id: str, *, mime_type: str | None) -> tuple[bytes, str]:
    from app.connectors.google_drive import GoogleDriveAPIError, download_file, export_file, get_file

    meta = get_file(access_token, file_id)
    name = str(meta.get("name") or file_id)
    file_mime = mime_type or str(meta.get("mimeType") or "")
    export_mime = _GOOGLE_NATIVE_EXPORT.get(file_mime)
    try:
        if export_mime:
            data = export_file(access_token, file_id, mime_type=export_mime)
            ext = ".txt" if export_mime == "text/plain" else ".csv"
            return data, f"{name}{ext}"
        data = download_file(access_token, file_id)
        return data, name
    except GoogleDriveAPIError as exc:
        if exc.status_code in {401, 403, 404}:
            raise ConnectedFileError(
                "Access to this file was denied or revoked in Google Drive.",
                code="permission_denied",
            ) from exc
        raise ConnectedFileError(str(exc), code="vendor_error") from exc


MAX_CHAT_ATTACHED_FILES = 5
_MAX_ATTACHMENT_EXCERPT_CHARS = 12_000


def refs_to_connected_file_hits(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for ref in refs[:MAX_CHAT_ATTACHED_FILES]:
        if not isinstance(ref, dict):
            continue
        file_id = str(ref.get("file_id") or ref.get("id") or "").strip()
        vendor = str(ref.get("vendor") or "").strip().lower()
        if not file_id or not vendor:
            continue
        hits.append(
            {
                "file_id": file_id,
                "name": str(ref.get("name") or "Untitled"),
                "vendor": vendor,
                "web_link": ref.get("web_link"),
                "path": ref.get("path") or ref.get("name"),
                "connector_id": ref.get("connector_id"),
            }
        )
    return hits


def build_connected_file_attachment_prompt(
    *,
    excerpts: list[dict[str, Any]],
) -> str:
    if not excerpts:
        return ""
    lines = [
        "Connected files (read-only for this turn): Gravitre did not upload or copy these files.",
        "They remain in the user's connected account; cite the vendor link when answering.",
        "",
    ]
    for item in excerpts:
        name = item.get("name") or "Untitled"
        vendor = item.get("vendor") or ""
        link = item.get("web_link") or ""
        lines.append(f"--- File: {name} ({vendor}) ---")
        if link:
            lines.append(f"Source link: {link}")
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(text[:_MAX_ATTACHMENT_EXCERPT_CHARS])
        elif item.get("error"):
            lines.append(f"(Could not read content: {item.get('error')})")
        lines.append("")
    return "\n".join(lines).strip()


async def prefetch_connected_file_attachments(
    ctx: "ToolContext",
    refs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Fetch live file text for composer attachments (transient only)."""
    import asyncio

    from app.services.connected_files_tools import CONNECTED_FILE_TOOLS
    from app.services.tool_types import ToolContext as ToolContextCls

    if not isinstance(ctx, ToolContextCls):
        raise TypeError("ctx must be ToolContext")

    hits = refs_to_connected_file_hits(refs)
    excerpts: list[dict[str, Any]] = []

    for hit in hits:
        vendor = hit["vendor"]
        action = f"{vendor}.get_file_content"
        executor = CONNECTED_FILE_TOOLS.get(action)
        if not executor:
            excerpts.append({**hit, "error": f"No reader for {vendor}"})
            continue
        params: dict[str, Any] = {"file_id": hit["file_id"]}
        if hit.get("connector_id"):
            params["connector_id"] = hit["connector_id"]
        try:
            result = await asyncio.to_thread(executor, ctx, params)
            data = result.data if hasattr(result, "data") else {}
            text = str((data or {}).get("text") or "")
            excerpts.append(
                {
                    **hit,
                    "text": text,
                    "truncated": bool((data or {}).get("truncated")),
                    "citation": (data or {}).get("citation"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            excerpts.append({**hit, "error": str(exc)})

    prompt_block = build_connected_file_attachment_prompt(excerpts=excerpts)
    return hits, prompt_block
