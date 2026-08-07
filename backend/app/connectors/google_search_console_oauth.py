"""Google Search Console site linking helpers (mirror GA4 property link)."""
from __future__ import annotations

from typing import Any
from app.core.safe_dict import safe_normalize_stored_dict


def normalize_gsc_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {
        "googlesearchconsole",
        "google_search_console",
        "searchconsole",
        "gsc",
        "webmasters",
    }:
        return "google_search_console"
    return key


def link_gsc_site(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    site_url: str,
    permission_level: str | None = None,
) -> None:
    url = site_url.strip()
    if not url:
        raise ValueError("site_url is required")
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    config["site_url"] = url
    config["siteUrl"] = url
    if permission_level:
        config["permission_level"] = permission_level
        config["permissionLevel"] = permission_level
    client.table("connectors").update({"config": config, "status": "connected"}).eq(
        "id", connector_id
    ).eq("org_id", org_id).execute()
