"""Package provenance helpers for private Git-backed marketplaces."""
from __future__ import annotations

import hashlib
import json
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
    publisher_verified: bool = False,
    source_uri: str | None = None,
) -> dict[str, object]:
    return {
        "publisherName": (publisher_name or "").strip() or None,
        "publisherVerified": bool(publisher_verified),
        "signatureStatus": signature_status,
        "contentDigest": bundle_digest(files or {}) if files else None,
        "sourceUri": source_uri,
    }


def inert_snapshot_digest(
    *,
    manifest: dict[str, object] | None,
    resources: list[dict[str, object]] | None,
) -> str:
    """Digest the reviewed inert Marketplace snapshot, never executable bytes."""
    normalized_resources = []
    for row in resources or []:
        path = str(row.get("path") or "").replace("\\", "/").lstrip("/")
        if not path:
            continue
        executable = bool(row.get("executable"))
        kind = str(row.get("kind") or "reference")
        normalized_resources.append(
            {
                "path": path,
                "kind": kind,
                "content": None if executable or kind == "script" else row.get("content"),
                "executable": executable,
            }
        )
    payload = {
        "manifest": manifest or {},
        "resources": sorted(normalized_resources, key=lambda row: row["path"]),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
