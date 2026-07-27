"""Google Ads API client (current Ads API REST — not legacy AdWords).

Uses GAQL via googleAds:search with allowlisted query builders only —
raw GAQL from the model is never accepted.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import httpx

GOOGLE_ADS_API_VERSION = "v25"
GOOGLE_ADS_API_BASE = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"
TIMEOUT_SEC = 45.0

_CUSTOMER_ID_RE = re.compile(r"^\d{6,12}$")
_RESOURCE_ID_RE = re.compile(r"^\d+$")


class GoogleAdsAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def normalize_customer_id(value: str | None) -> str:
    raw = str(value or "").strip().replace("-", "")
    if not _CUSTOMER_ID_RE.match(raw):
        raise GoogleAdsAPIError("customer_id must be a numeric Google Ads customer id")
    return raw


def campaign_ui_url(*, customer_id: str, campaign_id: str) -> str:
    cid = normalize_customer_id(customer_id)
    camp = str(campaign_id).strip()
    return f"https://ads.google.com/aw/campaigns?ocid={cid}&campaignId={camp}"


def _ads_headers(
    access_token: str,
    *,
    developer_token: str,
    login_customer_id: str | None = None,
) -> dict[str, str]:
    token = (developer_token or "").strip()
    if not token:
        raise GoogleAdsAPIError(
            "Google Ads developer token is not configured "
            "(set GOOGLE_ADS_DEVELOPER_TOKEN on the API)"
        )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = normalize_customer_id(login_customer_id)
    return headers


def _raise_for_status(response: httpx.Response, *, action: str) -> None:
    if response.status_code < 400:
        return
    details: Any
    try:
        details = response.json()
    except Exception:  # noqa: BLE001
        details = response.text
    raise GoogleAdsAPIError(
        f"Google Ads {action} {response.status_code}: {response.text[:400]}",
        status_code=response.status_code,
        details=details,
    )


def list_accessible_customers(
    access_token: str,
    *,
    developer_token: str,
) -> list[dict[str, str]]:
    """List customer resource names the OAuth user can access."""
    headers = _ads_headers(access_token, developer_token=developer_token)
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(
            f"{GOOGLE_ADS_API_BASE}/customers:listAccessibleCustomers",
            headers=headers,
        )
        _raise_for_status(response, action="customers:listAccessibleCustomers")
        data = response.json() or {}
    out: list[dict[str, str]] = []
    for resource in data.get("resourceNames") or []:
        name = str(resource or "").strip()
        # customers/1234567890
        cid = name.rsplit("/", 1)[-1] if "/" in name else name
        if _CUSTOMER_ID_RE.match(cid.replace("-", "")):
            out.append({"customer_id": cid.replace("-", ""), "resource_name": name})
    return out


def _search(
    access_token: str,
    customer_id: str,
    query: str,
    *,
    developer_token: str,
    login_customer_id: str | None = None,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    cid = normalize_customer_id(customer_id)
    headers = _ads_headers(
        access_token,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    body = {"query": query, "pageSize": max(1, min(int(page_size), 1000))}
    rows: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        while True:
            payload = dict(body)
            if page_token:
                payload["pageToken"] = page_token
            response = client.post(
                f"{GOOGLE_ADS_API_BASE}/customers/{cid}/googleAds:search",
                headers=headers,
                json=payload,
            )
            _raise_for_status(response, action="googleAds:search")
            data = response.json() or {}
            rows.extend(list(data.get("results") or []))
            page_token = str(data.get("nextPageToken") or "").strip() or None
            if not page_token:
                break
            if len(rows) >= page_size:
                break
    return rows


def list_campaigns(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    login_customer_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, "
        "campaign_budget.amount_micros, campaign_budget.resource_name "
        "FROM campaign "
        "WHERE campaign.status != 'REMOVED' "
        "ORDER BY campaign.name"
    )
    results = _search(
        access_token,
        customer_id,
        query,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        page_size=limit,
    )
    campaigns: list[dict[str, Any]] = []
    for row in results[:limit]:
        campaign = row.get("campaign") or {}
        budget = row.get("campaignBudget") or {}
        camp_id = str(campaign.get("id") or "")
        campaigns.append(
            {
                "id": camp_id,
                "name": campaign.get("name"),
                "status": campaign.get("status"),
                "channel_type": campaign.get("advertisingChannelType"),
                "budget_amount_micros": budget.get("amountMicros"),
                "budget_resource_name": budget.get("resourceName"),
                "resource_name": campaign.get("resourceName"),
                "result_url": campaign_ui_url(customer_id=customer_id, campaign_id=camp_id)
                if camp_id
                else "https://ads.google.com/",
            }
        )
    return campaigns


def get_campaign(
    access_token: str,
    customer_id: str,
    campaign_id: str,
    *,
    developer_token: str,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    camp_id = str(campaign_id or "").strip()
    if not _RESOURCE_ID_RE.match(camp_id):
        raise GoogleAdsAPIError("campaign_id must be numeric")
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, "
        "campaign.start_date, campaign.end_date, "
        "campaign_budget.amount_micros, campaign_budget.resource_name "
        "FROM campaign "
        f"WHERE campaign.id = {camp_id}"
    )
    results = _search(
        access_token,
        customer_id,
        query,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        page_size=1,
    )
    if not results:
        raise GoogleAdsAPIError(f"Campaign {camp_id} not found", status_code=404)
    campaign = results[0].get("campaign") or {}
    budget = results[0].get("campaignBudget") or {}
    return {
        "id": str(campaign.get("id") or camp_id),
        "name": campaign.get("name"),
        "status": campaign.get("status"),
        "channel_type": campaign.get("advertisingChannelType"),
        "start_date": campaign.get("startDate"),
        "end_date": campaign.get("endDate"),
        "budget_amount_micros": budget.get("amountMicros"),
        "budget_resource_name": budget.get("resourceName"),
        "resource_name": campaign.get("resourceName"),
        "result_url": campaign_ui_url(customer_id=customer_id, campaign_id=camp_id),
    }


def list_ad_groups(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_id: str | None = None,
    login_customer_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = ["ad_group.status != 'REMOVED'"]
    if campaign_id:
        cid = str(campaign_id).strip()
        if not _RESOURCE_ID_RE.match(cid):
            raise GoogleAdsAPIError("campaign_id must be numeric")
        clauses.append(f"campaign.id = {cid}")
    where = " AND ".join(clauses)
    query = (
        "SELECT ad_group.id, ad_group.name, ad_group.status, campaign.id, campaign.name "
        f"FROM ad_group WHERE {where} ORDER BY ad_group.name"
    )
    results = _search(
        access_token,
        customer_id,
        query,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        page_size=limit,
    )
    groups: list[dict[str, Any]] = []
    for row in results[:limit]:
        ag = row.get("adGroup") or {}
        camp = row.get("campaign") or {}
        groups.append(
            {
                "id": str(ag.get("id") or ""),
                "name": ag.get("name"),
                "status": ag.get("status"),
                "campaign_id": str(camp.get("id") or ""),
                "campaign_name": camp.get("name"),
                "resource_name": ag.get("resourceName"),
            }
        )
    return groups


def list_keywords(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    login_customer_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = [
        "ad_group_criterion.type = 'KEYWORD'",
        "ad_group_criterion.status != 'REMOVED'",
    ]
    if campaign_id:
        cid = str(campaign_id).strip()
        if not _RESOURCE_ID_RE.match(cid):
            raise GoogleAdsAPIError("campaign_id must be numeric")
        clauses.append(f"campaign.id = {cid}")
    if ad_group_id:
        agid = str(ad_group_id).strip()
        if not _RESOURCE_ID_RE.match(agid):
            raise GoogleAdsAPIError("ad_group_id must be numeric")
        clauses.append(f"ad_group.id = {agid}")
    where = " AND ".join(clauses)
    query = (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
        "ad_group.id, ad_group.name, campaign.id, campaign.name "
        f"FROM ad_group_criterion WHERE {where} ORDER BY ad_group_criterion.keyword.text"
    )
    results = _search(
        access_token,
        customer_id,
        query,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        page_size=limit,
    )
    keywords: list[dict[str, Any]] = []
    for row in results[:limit]:
        criterion = row.get("adGroupCriterion") or {}
        keyword = criterion.get("keyword") or {}
        ag = row.get("adGroup") or {}
        camp = row.get("campaign") or {}
        keywords.append(
            {
                "id": str(criterion.get("criterionId") or ""),
                "text": keyword.get("text"),
                "match_type": keyword.get("matchType"),
                "status": criterion.get("status"),
                "ad_group_id": str(ag.get("id") or ""),
                "ad_group_name": ag.get("name"),
                "campaign_id": str(camp.get("id") or ""),
                "campaign_name": camp.get("name"),
            }
        )
    return keywords


def _normalize_report_date(value: str, *, default_offset_days: int = 0) -> str:
    raw = str(value or "").strip()
    lowered = raw.lower()
    today = date.today()
    if lowered in {"today", ""}:
        return (today - timedelta(days=default_offset_days)).isoformat()
    if lowered == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    if lowered.endswith("daysago") and lowered[:-7].isdigit():
        return (today - timedelta(days=int(lowered[:-7]))).isoformat()
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return (today - timedelta(days=default_offset_days)).isoformat()


def performance_report(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    start_date: str = "7daysAgo",
    end_date: str = "yesterday",
    campaign_id: str | None = None,
    login_customer_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Safe performance report wrapper — fixed GAQL, no raw query injection."""
    start = _normalize_report_date(start_date, default_offset_days=7)
    end = _normalize_report_date(end_date, default_offset_days=1)
    clauses = [f"segments.date BETWEEN '{start}' AND '{end}'", "campaign.status != 'REMOVED'"]
    if campaign_id:
        cid = str(campaign_id).strip()
        if not _RESOURCE_ID_RE.match(cid):
            raise GoogleAdsAPIError("campaign_id must be numeric")
        clauses.append(f"campaign.id = {cid}")
    where = " AND ".join(clauses)
    query = (
        "SELECT campaign.id, campaign.name, segments.date, "
        "metrics.impressions, metrics.clicks, metrics.cost_micros, "
        "metrics.conversions, metrics.ctr, metrics.average_cpc "
        f"FROM campaign WHERE {where} "
        "ORDER BY segments.date DESC, metrics.cost_micros DESC"
    )
    results = _search(
        access_token,
        customer_id,
        query,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        page_size=limit,
    )
    rows_out: list[dict[str, Any]] = []
    for row in results[:limit]:
        campaign = row.get("campaign") or {}
        metrics = row.get("metrics") or {}
        segments = row.get("segments") or {}
        rows_out.append(
            {
                "campaign_id": str(campaign.get("id") or ""),
                "campaign_name": campaign.get("name"),
                "date": segments.get("date"),
                "impressions": metrics.get("impressions"),
                "clicks": metrics.get("clicks"),
                "cost_micros": metrics.get("costMicros"),
                "conversions": metrics.get("conversions"),
                "ctr": metrics.get("ctr"),
                "average_cpc": metrics.get("averageCpc"),
            }
        )
    return {
        "start_date": start,
        "end_date": end,
        "rows": rows_out,
        "result_url": f"https://ads.google.com/aw/campaigns?ocid={normalize_customer_id(customer_id)}",
    }


def _mutate_campaigns(
    access_token: str,
    customer_id: str,
    operations: list[dict[str, Any]],
    *,
    developer_token: str,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    cid = normalize_customer_id(customer_id)
    headers = _ads_headers(
        access_token,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{GOOGLE_ADS_API_BASE}/customers/{cid}/campaigns:mutate",
            headers=headers,
            json={"operations": operations},
        )
        _raise_for_status(response, action="campaigns:mutate")
        return response.json() or {}


def _mutate_campaign_budgets(
    access_token: str,
    customer_id: str,
    operations: list[dict[str, Any]],
    *,
    developer_token: str,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    cid = normalize_customer_id(customer_id)
    headers = _ads_headers(
        access_token,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{GOOGLE_ADS_API_BASE}/customers/{cid}/campaignBudgets:mutate",
            headers=headers,
            json={"operations": operations},
        )
        _raise_for_status(response, action="campaignBudgets:mutate")
        return response.json() or {}


def update_campaign_budget(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_id: str,
    amount_micros: int,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    detail = get_campaign(
        access_token,
        customer_id,
        campaign_id,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    budget_rn = str(detail.get("budget_resource_name") or "").strip()
    if not budget_rn:
        raise GoogleAdsAPIError("Campaign has no linked campaign budget resource")
    amount = int(amount_micros)
    if amount < 10_000:
        raise GoogleAdsAPIError("amount_micros must be at least 10000 (0.01 in account currency)")
    mutate = _mutate_campaign_budgets(
        access_token,
        customer_id,
        [
            {
                "updateMask": "amountMicros",
                "update": {
                    "resourceName": budget_rn,
                    "amountMicros": str(amount),
                },
            }
        ],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    return {
        "campaign_id": str(detail.get("id") or campaign_id),
        "campaign_name": detail.get("name"),
        "budget_resource_name": budget_rn,
        "amount_micros": amount,
        "result_url": detail.get("result_url"),
        "mutate": mutate,
    }


def set_campaign_status(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_id: str,
    status: str,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    camp_id = str(campaign_id or "").strip()
    if not _RESOURCE_ID_RE.match(camp_id):
        raise GoogleAdsAPIError("campaign_id must be numeric")
    status_norm = str(status or "").strip().upper()
    if status_norm not in {"PAUSED", "ENABLED"}:
        raise GoogleAdsAPIError("status must be PAUSED or ENABLED")
    cid = normalize_customer_id(customer_id)
    resource_name = f"customers/{cid}/campaigns/{camp_id}"
    mutate = _mutate_campaigns(
        access_token,
        customer_id,
        [
            {
                "updateMask": "status",
                "update": {
                    "resourceName": resource_name,
                    "status": status_norm,
                },
            }
        ],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    return {
        "campaign_id": camp_id,
        "status": status_norm,
        "resource_name": resource_name,
        "result_url": campaign_ui_url(customer_id=customer_id, campaign_id=camp_id),
        "mutate": mutate,
    }
