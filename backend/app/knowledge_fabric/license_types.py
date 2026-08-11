"""License classification A–E for knowledge fabric sources.

A–E remains the canonical gate. Additional fields on knowledge_sources
(license, license_url, derivatives_allowed, third_party_content_present,
legal_review_status) add granularity — they do not form a parallel scheme.

Proposed ingestion_policy vocabulary maps onto A–E + existing columns:

| Proposed policy     | Maps to |
|---------------------|---------|
| FULL                | A/B + commercial_use_allowed + bulk/api ingest |
| FILTERED            | A + third_party_content_present + provenance filter |
| API                 | B + ingestion_method=api |
| REFRESHABLE         | A/B + refresh_frequency daily/weekly/version_change |
| LIVE_RETRIEVAL      | D + ingestion_method=live_only + crawl_allowed=false |
| METADATA_ONLY       | registry row, hold_reason or no chunks |
| BLOCKED_LICENSE     | commercial_use_allowed=false (hard refuse) |
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


def assert_ingest_allowed(
    license_type: str,
    *,
    ingestion_method: str,
    crawl_allowed: bool,
    commercial_use_allowed: bool | None = None,
) -> None:
    """Hard gate for permanent platform_shared corpus writes.

    Refuses type D/C/E, and refuses any source where commercial_use is false
    or unconfirmed (None). Matches CI-lint discipline for A–E.
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


def license_implies_noncommercial(license_label: str | None) -> bool:
    text = (license_label or "").upper()
    return "NC" in text or "NONCOMMERCIAL" in text.replace("-", "").replace(" ", "")
