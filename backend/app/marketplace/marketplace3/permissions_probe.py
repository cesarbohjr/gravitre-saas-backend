"""Authenticated tenant-isolation probe for Marketplace 3.0 certification."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


def _config(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("configuration")
    return value if isinstance(value, dict) else {}


async def probe_outcome_pack_permissions(
    service_client: Any,
    settings: Settings,
    *,
    org_id: str,
    asset_id: str,
    access_token: str,
) -> dict[str, Any]:
    """Prove own-row visibility and cross-org non-enumeration under user RLS.

    The service-role client only selects control row ids. Visibility itself is
    tested through PostgREST with the caller's real access token.
    """
    if not access_token.strip():
        return {
            "passed": False,
            "reason": "access_token_missing",
            "ownVisible": False,
            "foreignHidden": False,
        }

    own_rows = (
        service_client.table("play_installations")
        .select("id, org_id, configuration")
        .eq("org_id", org_id)
        .limit(500)
        .execute()
        .data
        or []
    )
    own = next(
        (
            dict(row)
            for row in own_rows
            if str(_config(row).get("marketplaceAssetId") or "") == asset_id
        ),
        None,
    )
    if own is None:
        return {
            "passed": False,
            "reason": "outcome_pack_installation_missing",
            "ownVisible": False,
            "foreignHidden": False,
        }

    foreign_rows = (
        service_client.table("play_installations")
        .select("id, org_id")
        .neq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not foreign_rows:
        return {
            "passed": False,
            "reason": "foreign_control_row_unavailable",
            "ownVisible": False,
            "foreignHidden": False,
            "ownRowId": str(own.get("id") or ""),
        }

    foreign = dict(foreign_rows[0])
    headers = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    url = f"{settings.supabase_url_stripped}/rest/v1/play_installations"
    timeout = httpx.Timeout(10.0)

    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        own_response = await client.get(
            url,
            params={
                "select": "id,org_id",
                "id": f"eq.{own['id']}",
                "limit": "1",
            },
        )
        foreign_response = await client.get(
            url,
            params={
                "select": "id,org_id",
                "id": f"eq.{foreign['id']}",
                "limit": "1",
            },
        )

    if own_response.status_code >= 400 or foreign_response.status_code >= 400:
        return {
            "passed": False,
            "reason": "rls_probe_http_error",
            "ownStatus": own_response.status_code,
            "foreignStatus": foreign_response.status_code,
            "ownVisible": False,
            "foreignHidden": False,
        }

    own_payload = own_response.json()
    foreign_payload = foreign_response.json()
    own_visible = (
        isinstance(own_payload, list)
        and len(own_payload) == 1
        and str((own_payload[0] or {}).get("org_id") or "") == org_id
    )
    foreign_hidden = isinstance(foreign_payload, list) and len(foreign_payload) == 0

    return {
        "passed": own_visible and foreign_hidden,
        "reason": (
            "rls_isolation_verified"
            if own_visible and foreign_hidden
            else "rls_isolation_failed"
        ),
        "ownVisible": own_visible,
        "foreignHidden": foreign_hidden,
        "ownRowId": str(own.get("id") or ""),
        "foreignControlRowId": str(foreign.get("id") or ""),
    }
