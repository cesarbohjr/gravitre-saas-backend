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


def is_trusted_publisher_key(
    client: Any,
    *,
    org_id: str,
    publisher_name: str | None,
    public_key_pem: str,
) -> bool:
    name = normalize_publisher_name(publisher_name)
    if not name:
        return False
    fingerprint = public_key_fingerprint(public_key_pem)
    rows = (
        client.table("capability_trusted_publishers")
        .select("id")
        .eq("org_id", org_id)
        .eq("publisher_name", name)
        .eq("key_fingerprint", fingerprint)
        .eq("status", "active")
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def trust_publisher_key(
    client: Any,
    *,
    org_id: str,
    publisher_name: str,
    public_key_pem: str,
    user_id: str,
) -> dict[str, Any]:
    name = normalize_publisher_name(publisher_name)
    if not name:
        raise ValueError("Publisher name is required")
    fingerprint = public_key_fingerprint(public_key_pem)
    row = {
        "org_id": org_id,
        "publisher_name": name,
        "key_fingerprint": fingerprint,
        "public_key_pem": public_key_pem.strip(),
        "status": "active",
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
            .select("id,publisher_name,key_fingerprint,status,added_by,created_at,revoked_at")
            .eq("org_id", org_id)
            .order("publisher_name")
            .execute()
        )
        return list(response.data or [])
    except Exception:
        return []
