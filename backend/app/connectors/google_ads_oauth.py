"""Google Ads customer linking helpers (mirror GSC site / GA4 property link)."""
from __future__ import annotations

from typing import Any
from app.core.safe_dict import safe_normalize_stored_dict


def normalize_google_ads_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {
        "googleads",
        "google_ads",
        "adwords",  # legacy alias → modern vendor
        "ads",
    }:
        return "google_ads"
    return key


def link_google_ads_customer(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    customer_id: str,
    login_customer_id: str | None = None,
    descriptive_name: str | None = None,
) -> None:
    from app.connectors.google_ads import normalize_customer_id

    cid = normalize_customer_id(customer_id)
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    config["customer_id"] = cid
    config["customerId"] = cid
    if descriptive_name:
        config["customer_name"] = descriptive_name
        config["customerName"] = descriptive_name
    if login_customer_id:
        login = normalize_customer_id(login_customer_id)
        config["login_customer_id"] = login
        config["loginCustomerId"] = login
    client.table("connectors").update({"config": config, "status": "connected"}).eq(
        "id", connector_id
    ).eq("org_id", org_id).execute()
