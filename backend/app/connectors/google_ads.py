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
    # Ads API search rejects pageSize (PAGE_SIZE_NOT_SUPPORTED); page is fixed server-side.
    # Cap results client-side via page_size / caller limit.
    want = max(1, min(int(page_size), 10000))
    rows: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        while True:
            payload: dict[str, Any] = {"query": query}
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
            if len(rows) >= want:
                return rows[:want]
            page_token = str(data.get("nextPageToken") or "").strip() or None
            if not page_token:
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


_MATCH_TYPES = frozenset({"BROAD", "PHRASE", "EXACT"})
_BIDDING_TYPES = frozenset({"MAXIMIZE_CONVERSIONS", "TARGET_CPA", "TARGET_ROAS"})


def _resource_id_from_name(resource_name: str) -> str:
    return str(resource_name or "").rsplit("/", 1)[-1].strip()


def _mutate_resource(
    access_token: str,
    customer_id: str,
    *,
    resource_path: str,
    operations: list[dict[str, Any]],
    developer_token: str,
    login_customer_id: str | None = None,
    action: str,
) -> dict[str, Any]:
    cid = normalize_customer_id(customer_id)
    headers = _ads_headers(
        access_token,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{GOOGLE_ADS_API_BASE}/customers/{cid}/{resource_path}:mutate",
            headers=headers,
            json={"operations": operations, "partialFailure": True},
        )
        _raise_for_status(response, action=action)
        return response.json() or {}


def _dollars_to_micros(amount: float | int | str) -> int:
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise GoogleAdsAPIError("budget amount must be numeric") from exc
    if value <= 0:
        raise GoogleAdsAPIError("budget amount must be positive")
    micros = int(round(value * 1_000_000))
    if micros < 10_000:
        raise GoogleAdsAPIError("daily budget must be at least 0.01 in account currency")
    return micros


def create_campaign_budget(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    name: str,
    amount_micros: int,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    budget_name = str(name or "").strip() or "Gravitre budget"
    amount = int(amount_micros)
    if amount < 10_000:
        raise GoogleAdsAPIError("amount_micros must be at least 10000")
    mutate = _mutate_campaign_budgets(
        access_token,
        customer_id,
        [
            {
                "create": {
                    "name": budget_name[:255],
                    "amountMicros": str(amount),
                    "deliveryMethod": "STANDARD",
                    "explicitlyShared": False,
                }
            }
        ],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    results = list(mutate.get("results") or [])
    resource_name = str((results[0] or {}).get("resourceName") or "") if results else ""
    if not resource_name:
        raise GoogleAdsAPIError("campaign budget create returned no resourceName", details=mutate)
    return {
        "budget_resource_name": resource_name,
        "budget_id": _resource_id_from_name(resource_name),
        "amount_micros": amount,
        "mutate": mutate,
    }


def create_search_campaign(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    name: str,
    budget_resource_name: str,
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    status: str = "PAUSED",
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    camp_name = str(name or "").strip()
    if not camp_name:
        raise GoogleAdsAPIError("campaign name is required")
    budget_rn = str(budget_resource_name or "").strip()
    if not budget_rn.startswith("customers/"):
        raise GoogleAdsAPIError("budget_resource_name is required")
    status_norm = str(status or "PAUSED").strip().upper()
    if status_norm not in {"PAUSED", "ENABLED"}:
        raise GoogleAdsAPIError("status must be PAUSED or ENABLED")
    bidding = str(bidding_strategy or "MAXIMIZE_CONVERSIONS").strip().upper()
    if bidding not in _BIDDING_TYPES:
        raise GoogleAdsAPIError(
            "bidding_strategy must be MAXIMIZE_CONVERSIONS, TARGET_CPA, or TARGET_ROAS"
        )
    create_body: dict[str, Any] = {
        "name": camp_name[:255],
        "status": status_norm,
        "advertisingChannelType": "SEARCH",
        "campaignBudget": budget_rn,
        # Required by Ads API v25+ (EU Political Ads Regulation).
        "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "networkSettings": {
            "targetGoogleSearch": True,
            "targetSearchNetwork": True,
            "targetContentNetwork": False,
            "targetPartnerSearchNetwork": False,
        },
    }
    if bidding == "MAXIMIZE_CONVERSIONS":
        create_body["maximizeConversions"] = {}
    elif bidding == "TARGET_CPA":
        if not target_cpa_micros or int(target_cpa_micros) <= 0:
            raise GoogleAdsAPIError("target_cpa_micros is required for TARGET_CPA")
        create_body["targetCpa"] = {"targetCpaMicros": str(int(target_cpa_micros))}
    else:
        if target_roas is None or float(target_roas) <= 0:
            raise GoogleAdsAPIError("target_roas is required for TARGET_ROAS")
        create_body["targetRoas"] = {"targetRoas": float(target_roas)}

    mutate = _mutate_campaigns(
        access_token,
        customer_id,
        [{"create": create_body}],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )
    results = list(mutate.get("results") or [])
    resource_name = str((results[0] or {}).get("resourceName") or "") if results else ""
    if not resource_name:
        raise GoogleAdsAPIError("campaign create returned no resourceName", details=mutate)
    campaign_id = _resource_id_from_name(resource_name)
    return {
        "campaign_id": campaign_id,
        "campaign_resource_name": resource_name,
        "name": camp_name,
        "status": status_norm,
        "bidding_strategy": bidding,
        "result_url": campaign_ui_url(customer_id=customer_id, campaign_id=campaign_id),
        "mutate": mutate,
    }


def create_ad_group(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_resource_name: str,
    name: str,
    cpc_bid_micros: int = 1_000_000,
    status: str = "ENABLED",
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    group_name = str(name or "").strip()
    if not group_name:
        raise GoogleAdsAPIError("ad group name is required")
    campaign_rn = str(campaign_resource_name or "").strip()
    if not campaign_rn.startswith("customers/"):
        raise GoogleAdsAPIError("campaign_resource_name is required")
    status_norm = str(status or "ENABLED").strip().upper()
    mutate = _mutate_resource(
        access_token,
        customer_id,
        resource_path="adGroups",
        operations=[
            {
                "create": {
                    "name": group_name[:255],
                    "campaign": campaign_rn,
                    "status": status_norm,
                    "type": "SEARCH_STANDARD",
                    "cpcBidMicros": str(int(cpc_bid_micros)),
                }
            }
        ],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        action="adGroups:mutate",
    )
    results = list(mutate.get("results") or [])
    resource_name = str((results[0] or {}).get("resourceName") or "") if results else ""
    if not resource_name:
        raise GoogleAdsAPIError("ad group create returned no resourceName", details=mutate)
    return {
        "ad_group_id": _resource_id_from_name(resource_name),
        "ad_group_resource_name": resource_name,
        "name": group_name,
        "mutate": mutate,
    }


def create_ad_group_keywords(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    ad_group_resource_name: str,
    keywords: list[dict[str, str]],
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    ad_group_rn = str(ad_group_resource_name or "").strip()
    if not ad_group_rn.startswith("customers/"):
        raise GoogleAdsAPIError("ad_group_resource_name is required")
    operations: list[dict[str, Any]] = []
    for row in keywords or []:
        text = str((row or {}).get("text") or (row or {}).get("keyword") or "").strip()
        if not text:
            continue
        match = str((row or {}).get("match_type") or (row or {}).get("match") or "PHRASE").strip().upper()
        if match not in _MATCH_TYPES:
            match = "PHRASE"
        operations.append(
            {
                "create": {
                    "adGroup": ad_group_rn,
                    "status": "ENABLED",
                    "keyword": {"text": text[:80], "matchType": match},
                }
            }
        )
    if not operations:
        raise GoogleAdsAPIError("at least one keyword is required")
    mutate = _mutate_resource(
        access_token,
        customer_id,
        resource_path="adGroupCriteria",
        operations=operations,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        action="adGroupCriteria:mutate",
    )
    created: list[dict[str, str]] = []
    failures: list[dict[str, Any]] = []
    for idx, result in enumerate(mutate.get("results") or []):
        rn = str((result or {}).get("resourceName") or "").strip()
        if rn:
            created.append({"resource_name": rn, "criterion_id": _resource_id_from_name(rn)})
        else:
            failures.append({"index": idx, "result": result})
    partial = mutate.get("partialFailureError")
    if partial:
        failures.append({"partial_failure": partial})
    return {"created": created, "failures": failures, "mutate": mutate}


def add_campaign_negative_keywords(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    campaign_resource_name: str,
    keywords: list[str],
    match_type: str = "BROAD",
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    campaign_rn = str(campaign_resource_name or "").strip()
    if not campaign_rn.startswith("customers/"):
        raise GoogleAdsAPIError("campaign_resource_name is required")
    match = str(match_type or "BROAD").strip().upper()
    if match not in _MATCH_TYPES:
        match = "BROAD"
    operations: list[dict[str, Any]] = []
    for text in keywords or []:
        value = str(text or "").strip()
        if not value:
            continue
        operations.append(
            {
                "create": {
                    "campaign": campaign_rn,
                    "negative": True,
                    "keyword": {"text": value[:80], "matchType": match},
                }
            }
        )
    if not operations:
        raise GoogleAdsAPIError("at least one negative keyword is required")
    mutate = _mutate_resource(
        access_token,
        customer_id,
        resource_path="campaignCriteria",
        operations=operations,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        action="campaignCriteria:mutate",
    )
    return {"mutate": mutate, "count": len(operations)}


def create_conversion_action(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    name: str,
    category: str = "DEFAULT",
    default_value: float = 1.0,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    action_name = str(name or "").strip()
    if not action_name:
        raise GoogleAdsAPIError("conversion action name is required")
    mutate = _mutate_resource(
        access_token,
        customer_id,
        resource_path="conversionActions",
        operations=[
            {
                "create": {
                    "name": action_name[:100],
                    "type": "WEBPAGE",
                    "category": str(category or "DEFAULT").strip().upper() or "DEFAULT",
                    "status": "ENABLED",
                    "viewThroughLookbackWindowDays": "1",
                    "valueSettings": {
                        "defaultValue": float(default_value),
                        "alwaysUseDefaultValue": True,
                    },
                }
            }
        ],
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        action="conversionActions:mutate",
    )
    results = list(mutate.get("results") or [])
    resource_name = str((results[0] or {}).get("resourceName") or "") if results else ""
    return {
        "conversion_action_resource_name": resource_name,
        "conversion_action_id": _resource_id_from_name(resource_name) if resource_name else "",
        "name": action_name,
        "mutate": mutate,
    }


def create_search_campaign_structure(
    access_token: str,
    customer_id: str,
    *,
    developer_token: str,
    daily_budget_total: float,
    campaigns: list[dict[str, Any]],
    negative_keywords: list[str] | None = None,
    conversion_actions: list[dict[str, Any]] | None = None,
    status: str = "PAUSED",
    login_customer_id: str | None = None,
) -> dict[str, Any]:
    """Create Search campaigns + ad groups + keywords + shared negatives.

    Campaigns are created PAUSED by default so approval does not spend until enabled.
    """
    if not campaigns:
        raise GoogleAdsAPIError("campaigns array is required")
    total_micros = _dollars_to_micros(daily_budget_total)
    weights = [float(c.get("budget_weight") or 0) for c in campaigns]
    weight_sum = sum(w for w in weights if w > 0) or float(len(campaigns))
    created_campaigns: list[dict[str, Any]] = []
    keyword_failures: list[dict[str, Any]] = []
    created_conversions: list[dict[str, Any]] = []

    for action in conversion_actions or []:
        if not isinstance(action, dict):
            continue
        created_conversions.append(
            create_conversion_action(
                access_token,
                customer_id,
                developer_token=developer_token,
                name=str(action.get("name") or ""),
                category=str(action.get("category") or "DEFAULT"),
                default_value=float(action.get("default_value") or action.get("value") or 1.0),
                login_customer_id=login_customer_id,
            )
        )

    for idx, campaign in enumerate(campaigns):
        if not isinstance(campaign, dict):
            continue
        name = str(campaign.get("name") or f"Campaign {idx + 1}").strip()
        weight = float(campaign.get("budget_weight") or (1.0 / len(campaigns)))
        if weight <= 0:
            weight = 1.0 / len(campaigns)
        amount_micros = max(10_000, int(round(total_micros * (weight / weight_sum))))
        bidding = str(
            campaign.get("bidding_strategy")
            or (campaign.get("bidding") or {}).get("type")
            or "MAXIMIZE_CONVERSIONS"
        ).upper()
        target_cpa = campaign.get("target_cpa_micros") or (campaign.get("bidding") or {}).get(
            "target_cpa_micros"
        )
        target_roas = campaign.get("target_roas") or (campaign.get("bidding") or {}).get("target_roas")

        budget = create_campaign_budget(
            access_token,
            customer_id,
            developer_token=developer_token,
            name=f"{name} budget",
            amount_micros=amount_micros,
            login_customer_id=login_customer_id,
        )
        camp = create_search_campaign(
            access_token,
            customer_id,
            developer_token=developer_token,
            name=name,
            budget_resource_name=budget["budget_resource_name"],
            bidding_strategy=bidding,
            target_cpa_micros=int(target_cpa) if target_cpa else None,
            target_roas=float(target_roas) if target_roas is not None else None,
            status=status,
            login_customer_id=login_customer_id,
        )
        ad_groups_out: list[dict[str, Any]] = []
        for ag in campaign.get("ad_groups") or []:
            if not isinstance(ag, dict):
                continue
            ag_name = str(ag.get("name") or "").strip()
            if not ag_name:
                continue
            group = create_ad_group(
                access_token,
                customer_id,
                developer_token=developer_token,
                campaign_resource_name=camp["campaign_resource_name"],
                name=ag_name,
                login_customer_id=login_customer_id,
            )
            kw_rows = list(ag.get("keywords") or [])
            kw_result: dict[str, Any] = {"created": [], "failures": []}
            if kw_rows:
                kw_result = create_ad_group_keywords(
                    access_token,
                    customer_id,
                    developer_token=developer_token,
                    ad_group_resource_name=group["ad_group_resource_name"],
                    keywords=kw_rows,
                    login_customer_id=login_customer_id,
                )
                for fail in kw_result.get("failures") or []:
                    keyword_failures.append(
                        {"campaign": name, "ad_group": ag_name, "failure": fail}
                    )
            ad_groups_out.append({**group, "keywords": kw_result})

        negatives = list(negative_keywords or []) + list(campaign.get("negative_keywords") or [])
        neg_result = None
        if negatives:
            neg_result = add_campaign_negative_keywords(
                access_token,
                customer_id,
                developer_token=developer_token,
                campaign_resource_name=camp["campaign_resource_name"],
                keywords=[str(x) for x in negatives],
                login_customer_id=login_customer_id,
            )
        created_campaigns.append(
            {
                **camp,
                "daily_budget_micros": amount_micros,
                "budget_weight": weight,
                "ad_groups": ad_groups_out,
                "negatives": neg_result,
            }
        )

    return {
        "customer_id": normalize_customer_id(customer_id),
        "daily_budget_total_micros": total_micros,
        "status": str(status or "PAUSED").upper(),
        "campaigns": created_campaigns,
        "conversion_actions": created_conversions,
        "keyword_failures": keyword_failures,
        "result_url": f"https://ads.google.com/aw/campaigns?ocid={normalize_customer_id(customer_id)}",
        "note": (
            "Campaigns created PAUSED by default. Enable in Google Ads after reviewing "
            "structure, ads/RSA creative, and conversion tagging."
        ),
    }
