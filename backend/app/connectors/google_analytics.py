"""Google Analytics Admin API helpers (GA4 property listing)."""
from __future__ import annotations

from typing import Any

import httpx

GA_ADMIN_API = "https://analyticsadmin.googleapis.com/v1beta"


class GoogleAnalyticsAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _property_id_from_resource(resource: str) -> str:
    if resource.startswith("properties/"):
        return resource.split("/", 1)[1]
    return resource


def list_ga4_properties(access_token: str) -> list[dict[str, Any]]:
    """List GA4 properties available to the connected Google account."""
    headers = {"Authorization": f"Bearer {access_token}"}
    properties: list[dict[str, Any]] = []
    page_token: str | None = None

    with httpx.Client(timeout=30.0) as client:
        while True:
            params: dict[str, str] = {"pageSize": "200"}
            if page_token:
                params["pageToken"] = page_token
            response = client.get(
                f"{GA_ADMIN_API}/accountSummaries",
                headers=headers,
                params=params,
            )
            if response.status_code >= 400:
                raise GoogleAnalyticsAPIError(
                    f"Analytics Admin API {response.status_code}",
                    status_code=response.status_code,
                )
            data = response.json()
            for summary in data.get("accountSummaries") or []:
                account = str(summary.get("account") or "")
                account_name = summary.get("displayName")
                for prop in summary.get("propertySummaries") or []:
                    resource = str(prop.get("property") or "")
                    if not resource:
                        continue
                    properties.append(
                        {
                            "property_id": _property_id_from_resource(resource),
                            "property_resource": resource,
                            "display_name": prop.get("displayName"),
                            "account": account,
                            "account_name": account_name,
                            "property_type": prop.get("propertyType"),
                        }
                    )
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    return properties


GA_DATA_API = "https://analyticsdata.googleapis.com/v1beta"


def run_ga4_report(
    access_token: str,
    property_id: str,
    *,
    start_date: str = "7daysAgo",
    end_date: str = "today",
    dimensions: list[str] | None = None,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Run a GA4 Data API report (STA-41)."""
    dims = dimensions or ["sessionCampaignName"]
    mets = metrics or ["sessions", "conversions"]
    body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": d} for d in dims],
        "metrics": [{"name": m} for m in mets],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{GA_DATA_API}/properties/{property_id}:runReport",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if response.status_code >= 400:
        raise GoogleAnalyticsAPIError(
            f"Analytics Data API {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()
