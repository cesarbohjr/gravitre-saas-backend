"""License classification A–E for knowledge fabric sources.

A–E remains the canonical gate. Additional fields on knowledge_sources
add granularity — they do not form a parallel scheme.
"""
from __future__ import annotations

from typing import Literal

LicenseType = Literal["A", "B", "C", "D", "E"]

LICENSE_TYPES: frozenset[str] = frozenset({"A", "B", "C", "D", "E"})

LICENSE_LABELS: dict[str, str] = {
    "A": "open_public_domain_or_explicit_reuse",
    "B": "api_licensed",
    "C": "commercially_licensed",
    "D": "public_web_unclear_reuse_live_only",
    "E": "customer_owned_private_tenant",
}

LEGAL_REVIEW_STATUSES: frozenset[str] = frozenset(
    {
        "unreviewed",
        "verified_live",
        "filtered_provenance",
        "blocked_nc",
        "blocked_unconfirmed",
        "live_retrieval_only",
        "pending_credentials",
    }
)

# Saylor resource-level allow/block (not course-level)
SAYLOR_ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-3.0",
        "CC-BY-4.0",
        "CC-BY-SA-3.0",
        "CC-BY-SA-4.0",
    }
)
SAYLOR_BLOCKED_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-NC",
        "CC-BY-NC-SA",
        "CC-BY-NC-3.0",
        "CC-BY-NC-4.0",
        "CC-BY-NC-SA-3.0",
        "CC-BY-NC-SA-4.0",
        "ARR",
        "UNKNOWN",
    }
)


def validate_license_type(value: str) -> str:
    code = (value or "").strip().upper()
    if code not in LICENSE_TYPES:
        raise ValueError(f"license_type must be A–E, got {value!r}")
    return code


def validate_legal_review_status(value: str | None) -> str:
    status = (value or "unreviewed").strip().lower()
    if status not in LEGAL_REVIEW_STATUSES:
        raise ValueError(f"legal_review_status invalid: {value!r}")
    return status


def normalize_saylor_resource_license(raw: str | None) -> str:
    """Map free-text license markers to structured Saylor allow/block codes."""
    text = (raw or "").upper().replace(" ", "")
    if not text:
        return "UNKNOWN"
    if "ALLRIGHTSRESERVED" in text or text == "ARR":
        return "ARR"
    if "BY-NC-SA" in text or "BYNCSA" in text:
        if "4.0" in text:
            return "CC-BY-NC-SA-4.0"
        if "3.0" in text:
            return "CC-BY-NC-SA-3.0"
        return "CC-BY-NC-SA"
    if "BY-NC" in text or "BYNC" in text or "NONCOMMERCIAL" in text:
        if "4.0" in text:
            return "CC-BY-NC-4.0"
        if "3.0" in text:
            return "CC-BY-NC-3.0"
        return "CC-BY-NC"
    if "BY-SA" in text or "BYSA" in text:
        if "4.0" in text:
            return "CC-BY-SA-4.0"
        return "CC-BY-SA-3.0"
    if "CCBY" in text.replace("-", "") or "CREATIVECOMMONSATTRIBUTION" in text.replace("-", ""):
        if "4.0" in text:
            return "CC-BY-4.0"
        return "CC-BY-3.0"
    return "UNKNOWN"


def saylor_resource_allowed(license_code: str) -> bool:
    code = (license_code or "UNKNOWN").strip().upper()
    if code in SAYLOR_BLOCKED_LICENSES or code.startswith("CC-BY-NC"):
        return False
    return code in SAYLOR_ALLOWED_LICENSES


def assert_ingest_allowed(
    license_type: str,
    *,
    ingestion_method: str,
    crawl_allowed: bool,
    commercial_use_allowed: bool | None = None,
    licence_verified: bool | None = None,
) -> None:
    """Hard gate for permanent platform_shared corpus writes.

    Refuses type D/C/E, commercial_use false/unconfirmed, and unverified licenses
    (OpenStax lesson: prior research ≠ live confirmation).
    """
    code = validate_license_type(license_type)
    if code == "D":
        if ingestion_method != "live_only" or crawl_allowed:
            raise ValueError("Type D sources must be live_only with crawl_allowed=false")
        raise ValueError("Type D must not be permanently ingested into knowledge_* tables")
    if code == "C":
        raise ValueError("Type C requires a confirmed commercial license before ingest")
    if code == "E":
        raise ValueError("Type E belongs in customer-private rag_* only, not platform knowledge_*")
    if commercial_use_allowed is not True:
        raise ValueError(
            "commercial_use_allowed must be true to ingest into the shared platform corpus "
            f"(got {commercial_use_allowed!r}) — NC / unconfirmed licenses are blocked"
        )
    if licence_verified is not True:
        raise ValueError(
            "licence_verified must be true before shared-corpus ingest "
            f"(got {licence_verified!r}) — live license confirmation required"
        )


def license_implies_noncommercial(license_label: str | None) -> bool:
    text = (license_label or "").upper()
    return "NC" in text or "NONCOMMERCIAL" in text.replace("-", "").replace(" ", "")
