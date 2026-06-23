"""Extract plain text from uploaded knowledge files for RAG ingest (STA-279)."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.rag.ingest import MAX_TEXT_BYTES

MAX_FILE_BYTES = MAX_TEXT_BYTES

_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".html", ".htm", ".log"}
_PDF_EXTENSIONS = {".pdf"}
_DOCX_EXTENSIONS = {".docx"}


class UnsupportedFileTypeError(ValueError):
    """Raised when the uploaded file type cannot be converted to text."""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("File is not valid UTF-8 or Latin-1 text")


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    if dot < 0:
        return ""
    return filename[dot:].lower()


def _extract_csv_text(raw: str) -> str:
    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(raw), dialect)
    rows: list[str] = []
    for row in reader:
        if not row:
            continue
        rows.append(" | ".join(cell.strip() for cell in row if cell.strip()))
    return "\n".join(rows).strip()


def _extract_json_text(raw: str) -> str:
    payload = json.loads(raw)
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UnsupportedFileTypeError(
            "PDF upload requires pypdf; install backend requirements or paste text instead"
        ) from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)
    if not pages:
        raise ValueError("PDF contains no extractable text")
    return "\n\n".join(pages)


def _extract_docx_text(data: bytes) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:
        raise UnsupportedFileTypeError(
            "DOCX upload requires python-docx; install backend requirements or paste text instead"
        ) from exc

    document = DocxDocument(io.BytesIO(data))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    if not paragraphs:
        raise ValueError("DOCX contains no extractable text")
    return "\n\n".join(paragraphs)


def supported_upload_extensions() -> set[str]:
    return _TEXT_EXTENSIONS | _PDF_EXTENSIONS | _DOCX_EXTENSIONS


def extract_text_from_bytes(data: bytes, filename: str, *, content_type: str | None = None) -> str:
    """Return UTF-8 text extracted from file bytes for RAG chunking."""
    if not data:
        raise ValueError("Uploaded file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("File exceeds maximum size")

    ext = _extension(filename or "")
    if not ext and content_type:
        lowered = content_type.lower()
        if "pdf" in lowered:
            ext = ".pdf"
        elif "json" in lowered:
            ext = ".json"
        elif "csv" in lowered:
            ext = ".csv"
        elif "html" in lowered:
            ext = ".html"
        elif "wordprocessingml" in lowered or "docx" in lowered:
            ext = ".docx"
        elif "text" in lowered:
            ext = ".txt"

    if ext in _PDF_EXTENSIONS:
        text = _extract_pdf_text(data)
    elif ext in _DOCX_EXTENSIONS:
        text = _extract_docx_text(data)
    elif ext in {".csv", ".tsv"}:
        text = _extract_csv_text(_decode_text(data))
    elif ext == ".json":
        text = _extract_json_text(_decode_text(data))
    elif ext in _TEXT_EXTENSIONS or ext == "":
        text = _decode_text(data)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type {ext or '(no extension)'}; "
            f"supported: {', '.join(sorted(supported_upload_extensions()))}"
        )

    text = text.strip()
    if not text:
        raise ValueError("File produced no text content")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Extracted text exceeds maximum size")
    return text


def ingest_metadata_from_upload(
    filename: str,
    *,
    content_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build rag document metadata for file-based ingest jobs."""
    meta: dict[str, Any] = {
        "ingest_kind": "file_upload",
        "original_filename": filename,
    }
    if content_type:
        meta["content_type"] = content_type
    if extra:
        meta.update(extra)
    return meta
