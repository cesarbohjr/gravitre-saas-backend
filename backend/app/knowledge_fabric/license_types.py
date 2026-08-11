"""License classification A–E for knowledge fabric sources."""
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


def validate_license_type(value: str) -> str:
    code = (value or "").strip().upper()
    if code not in LICENSE_TYPES:
        raise ValueError(f"license_type must be A–E, got {value!r}")
    return code


def assert_ingest_allowed(license_type: str, *, ingestion_method: str, crawl_allowed: bool) -> None:
    code = validate_license_type(license_type)
    if code == "D":
        if ingestion_method != "live_only" or crawl_allowed:
            raise ValueError("Type D sources must be live_only with crawl_allowed=false")
        raise ValueError("Type D must not be permanently ingested into knowledge_* tables")
    if code == "C":
        raise ValueError("Type C requires a confirmed commercial license before ingest")
    if code == "E":
        raise ValueError("Type E belongs in customer-private rag_* only, not platform knowledge_*")
