"""Package provenance helpers for private Git-backed marketplaces."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

_GITHUB_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_github_repository_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("Only https://github.com repository URLs are supported")
    path = parsed.path.strip("/").removesuffix(".git")
    if not _GITHUB_REPO.fullmatch(path):
        raise ValueError("GitHub source must point to one owner/repository")
    return f"https://github.com/{path}"


def bundle_digest(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        normalized = str(path).replace("\\", "/").lstrip("/")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(files[path]).encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def provenance_summary(
    *,
    files: dict[str, str] | None = None,
    publisher_name: str | None = None,
    signature_status: str = "unsigned",
    source_uri: str | None = None,
) -> dict[str, object]:
    return {
        "publisherName": (publisher_name or "").strip() or None,
        "publisherVerified": signature_status == "verified",
        "signatureStatus": signature_status,
        "contentDigest": bundle_digest(files or {}) if files else None,
        "sourceUri": source_uri,
    }


def publisher_declaration_candidates(manifest: dict[str, object]) -> set[str]:
    raw = manifest.get("publisher")
    if raw in (None, ""):
        raw = manifest.get("author")
    values: list[object] = []
    if isinstance(raw, str):
        values.append(raw)
    elif isinstance(raw, dict):
        values.extend([raw.get("slug"), raw.get("name"), raw.get("displayName")])
    return {
        str(value).strip().lower()
        for value in values
        if str(value or "").strip()
    }


def resolve_org_marketplace_publisher(
    client: object,
    *,
    org_id: str,
    manifest: dict[str, object],
) -> dict[str, object] | None:
    candidates = publisher_declaration_candidates(manifest)
    if not candidates:
        return None
    response = (
        client.table("marketplace_publishers")
        .select("id,slug,display_name,verified,status,org_id")
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    for row in list(response.data or []):
        slug = str(row.get("slug") or "").strip().lower()
        display_name = str(row.get("display_name") or "").strip().lower()
        if slug in candidates or display_name in candidates:
            return dict(row)
    return None
