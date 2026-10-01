"""Organization-scoped trust for portable capability publisher signing keys."""
from __future__ import annotations

import hashlib
from typing import Any

from cryptography.hazmat.primitives import serialization


def normalize_publisher_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def public_key_fingerprint(public_key_pem: str) -> str:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid publisher public key") from exc
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return f"sha256:{hashlib.sha256(der).hexdigest()}"


def publisher_trust_details(
    client: Any,
    *,
    org_id: str,
    publisher_name: str | None,
    public_key_pem: str,
) -> dict[str, Any]:
    name = normalize_publisher_name(publisher_name)
    if not name:
        return {
            "organizationTrusted": False,
            "marketplaceVerified": False,
            "marketplacePublisherId": None,
            "trustScope": "none",
        }
    fingerprint = public_key_fingerprint(public_key_pem)
    rows = (
        client.table("capability_trusted_publishers")
        .select("id,marketplace_publisher_id")
        .eq("org_id", org_id)
        .eq("publisher_name", name)
        .eq("key_fingerprint", fingerprint)
        .eq("status", "active")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return {
            "organizationTrusted": False,
            "marketplaceVerified": False,
            "marketplacePublisherId": None,
            "trustScope": "none",
        }
    marketplace_publisher_id = rows[0].get("marketplace_publisher_id")
    marketplace_verified = False
    if marketplace_publisher_id:
        publisher_rows = (
            client.table("marketplace_publishers")
            .select("id,verified,status")
            .eq("id", marketplace_publisher_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if publisher_rows:
            publisher = publisher_rows[0]
            marketplace_verified = bool(publisher.get("verified")) and str(publisher.get("status") or "") == "active"
    return {
        "organizationTrusted": True,
        "marketplaceVerified": marketplace_verified,
        "marketplacePublisherId": marketplace_publisher_id,
        "trustScope": "marketplace_verified" if marketplace_verified else "organization",
    }


def is_trusted_publisher_key(
    client: Any,
    *,
    org_id: str,
    publisher_name: str | None,
    public_key_pem: str,
) -> bool:
    details = publisher_trust_details(
        client,
        org_id=org_id,
        publisher_name=publisher_name,
        public_key_pem=public_key_pem,
    )
    return bool(details["organizationTrusted"])


def trust_publisher_key(
    client: Any,
    *,
    org_id: str,
    publisher_name: str,
    public_key_pem: str,
    user_id: str,
    marketplace_publisher_slug: str | None = None,
) -> dict[str, Any]:
    name = normalize_publisher_name(publisher_name)
    if not name:
        raise ValueError("Publisher name is required")
    fingerprint = public_key_fingerprint(public_key_pem)
    marketplace_publisher_id = None
    if marketplace_publisher_slug:
        publisher_rows = (
            client.table("marketplace_publishers")
            .select("id,slug,status")
            .eq("slug", marketplace_publisher_slug.strip().lower())
            .eq("status", "active")
            .limit(1)
            .execute()
            .data
            or []
        )
        if not publisher_rows:
            raise ValueError("Marketplace publisher slug was not found or is not active")
        marketplace_publisher_id = publisher_rows[0]["id"]
    row = {
        "org_id": org_id,
        "publisher_name": name,
        "key_fingerprint": fingerprint,
        "public_key_pem": public_key_pem.strip(),
        "status": "active",
        "marketplace_publisher_id": marketplace_publisher_id,
        "added_by": user_id or None,
        "revoked_at": None,
    }
    response = client.table("capability_trusted_publishers").upsert(
        row,
        on_conflict="org_id,publisher_name,key_fingerprint",
    ).execute()
    rows = list(response.data or [])
    return rows[0] if rows else row


def list_trusted_publishers(client: Any, org_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("capability_trusted_publishers")
            .select("id,publisher_name,key_fingerprint,marketplace_publisher_id,status,added_by,created_at,revoked_at")
            .eq("org_id", org_id)
            .order("publisher_name")
            .execute()
        )
        return list(response.data or [])
    except Exception:
        return []
