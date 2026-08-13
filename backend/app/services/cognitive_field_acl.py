"""Org field-level ACL helpers for CognitiveTurnKernel GOVERN (Phase 7)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def assert_field_allowed(
    client: Any,
    org_id: str,
    role: str,
    resource: str,
    field_key: str,
) -> bool:
    """
    Return True if the role may read/use ``field_key`` on ``resource``.

    Default allow when no rows exist for the (org, role, resource, field) tuple.
    Explicit deny wins; explicit allow permits.
    Always scoped by ``org_id``.
    """
    if not org_id or not field_key:
        return True
    if client is None:
        return True

    try:
        rows = (
            client.table("org_field_permissions")
            .select("effect, role, resource, field_key")
            .eq("org_id", org_id)
            .eq("resource", resource)
            .eq("field_key", field_key)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_field_acl_query_skipped error=%s", exc)
        return True

    if not rows:
        return True

    role_norm = (role or "").strip().lower()
    matching = [
        r
        for r in rows
        if isinstance(r, dict)
        and (
            not str(r.get("role") or "").strip()
            or str(r.get("role") or "").strip().lower() == role_norm
            or str(r.get("role") or "").strip() == "*"
        )
    ]
    if not matching:
        return True

    for row in matching:
        effect = str(row.get("effect") or "").strip().lower()
        if effect == "deny":
            return False
    for row in matching:
        effect = str(row.get("effect") or "").strip().lower()
        if effect == "allow":
            return True
    # Rows existed but no clear allow after deny check → treat as deny-safe default when
    # only non-matching effects; otherwise allow.
    return True


def redact_payload(payload: Any, denied_fields: list[str] | set[str] | None) -> Any:
    """Remove or null denied field keys from a dict payload (shallow + one-level nested)."""
    denied = {str(f) for f in (denied_fields or []) if f}
    if not denied:
        return payload
    if isinstance(payload, list):
        return [redact_payload(item, denied) for item in payload]
    if not isinstance(payload, dict):
        return payload

    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key in denied:
            continue
        if isinstance(value, dict):
            nested = {k: v for k, v in value.items() if k not in denied}
            out[key] = nested
        elif isinstance(value, list):
            out[key] = [
                ({k: v for k, v in item.items() if k not in denied} if isinstance(item, dict) else item)
                for item in value
            ]
        else:
            out[key] = value
    return out
