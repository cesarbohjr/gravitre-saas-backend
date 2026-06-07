"""Workday REST API client (STA-60).

v1 read: workers.get (by email/id), orgunits.list, timeoff.balance.get, positions.list
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class WorkdayAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    api_base_url: str,
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, params=params)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise WorkdayAPIError(
                    f"Workday API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()
        except WorkdayAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise WorkdayAPIError("Workday API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise WorkdayAPIError(str(exc)) from exc
    raise WorkdayAPIError(str(last_error or "Workday API request failed"))


def _paginate(
    api_base_url: str,
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset = 0
    page_size = max(1, min(int(limit), 100))
    base_params = dict(params or {})
    while len(items) < limit:
        query = dict(base_params)
        query["limit"] = min(page_size, limit - len(items))
        query["offset"] = offset
        data = _request("GET", api_base_url, access_token, path, params=query)
        batch = data.get("data") or data.get("results") or []
        if isinstance(batch, list):
            for item in batch:
                if isinstance(item, dict):
                    items.append(dict(item))
        total = data.get("total")
        if not batch:
            break
        offset += len(batch)
        if isinstance(total, int) and offset >= total:
            break
        if len(batch) < query["limit"]:
            break
    return items[:limit]


def normalize_worker(worker: dict[str, Any]) -> dict[str, Any]:
    primary_email = ""
    emails = worker.get("emails") or worker.get("emailAddresses") or []
    if isinstance(emails, list) and emails:
        first = emails[0]
        if isinstance(first, dict):
            primary_email = str(first.get("email") or first.get("emailAddress") or "")
        else:
            primary_email = str(first)
    return {
        "id": str(worker.get("id") or worker.get("workerId") or ""),
        "descriptor": str(worker.get("descriptor") or worker.get("name") or ""),
        "email": primary_email,
        "business_title": str(worker.get("businessTitle") or worker.get("title") or ""),
        "worker_type": str(worker.get("workerType") or ""),
        "supervisory_organization": worker.get("supervisoryOrganization"),
    }


def normalize_org_unit(org_unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(org_unit.get("id") or ""),
        "descriptor": str(org_unit.get("descriptor") or org_unit.get("name") or ""),
        "code": str(org_unit.get("code") or ""),
        "inactive": bool(org_unit.get("inactive") or org_unit.get("isInactive")),
    }


def normalize_position(position: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(position.get("id") or position.get("jobRequisitionId") or ""),
        "descriptor": str(position.get("descriptor") or position.get("title") or ""),
        "status": str(position.get("status") or position.get("requisitionStatus") or ""),
        "openings": position.get("openings") or position.get("numberOfOpenings"),
    }


def normalize_timeoff_balance(balance: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(balance.get("id") or ""),
        "descriptor": str(balance.get("descriptor") or balance.get("timeOffPlan") or ""),
        "unit": str(balance.get("unit") or balance.get("unitOfTime") or ""),
        "quantity": balance.get("quantity") or balance.get("balance"),
    }


def get_worker(
    api_base_url: str,
    access_token: str,
    *,
    worker_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    if worker_id:
        data = _request(
            "GET",
            api_base_url,
            access_token,
            f"/workers/{quote(str(worker_id), safe='')}",
        )
        worker = data.get("worker") if isinstance(data.get("worker"), dict) else data
        if not isinstance(worker, dict):
            raise WorkdayAPIError("Worker not found", status_code=404)
        return normalize_worker(worker)

    if email:
        results = search_workers(api_base_url, access_token, email=str(email), limit=5)
        workers = results.get("workers") or []
        if not workers:
            raise WorkdayAPIError("Worker not found for email", status_code=404)
        return workers[0]

    raise WorkdayAPIError(
        "get_worker requires worker_id or email",
        status_code=400,
    )


def search_workers(
    api_base_url: str,
    access_token: str,
    *,
    email: str | None = None,
    search: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 100))}
    if email:
        params["email"] = email
    if search:
        params["search"] = search
    data = _request("GET", api_base_url, access_token, "/workers", params=params)
    workers = data.get("data") or []
    normalized = [normalize_worker(item) for item in workers if isinstance(item, dict)]
    return {"workers": normalized, "total": data.get("total", len(normalized))}


def list_org_units(
    api_base_url: str,
    access_token: str,
    *,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if search:
        params["search"] = search
    org_units = _paginate(
        api_base_url,
        access_token,
        "/supervisoryOrganizations",
        params=params,
        limit=limit,
    )
    normalized = [normalize_org_unit(item) for item in org_units]
    return {"org_units": normalized, "total": len(normalized)}


def get_timeoff_balance(
    api_base_url: str,
    access_token: str,
    *,
    worker_id: str,
    time_off_plan_id: str | None = None,
) -> dict[str, Any]:
    wid = quote(str(worker_id), safe="")
    if time_off_plan_id:
        path = (
            f"/workers/{wid}/timeOffPlans/"
            f"{quote(str(time_off_plan_id), safe='')}/timeOffBalances"
        )
        data = _request("GET", api_base_url, access_token, path)
        balances = data.get("data") or []
    else:
        plans = _request("GET", api_base_url, access_token, f"/workers/{wid}/timeOffPlans")
        plan_items = plans.get("data") or []
        balances = []
        for plan in plan_items:
            if not isinstance(plan, dict) or not plan.get("id"):
                continue
            plan_id = quote(str(plan["id"]), safe="")
            balance_data = _request(
                "GET",
                api_base_url,
                access_token,
                f"/workers/{wid}/timeOffPlans/{plan_id}/timeOffBalances",
            )
            batch = balance_data.get("data") or []
            if isinstance(batch, list):
                balances.extend(batch)
    normalized = [
        normalize_timeoff_balance(item) for item in balances if isinstance(item, dict)
    ]
    return {"worker_id": str(worker_id), "balances": normalized, "total": len(normalized)}


def list_positions(
    api_base_url: str,
    access_token: str,
    *,
    limit: int = 50,
    status: str | None = "OPEN",
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if status:
        params["status"] = status
    positions = _paginate(
        api_base_url,
        access_token,
        "/jobRequisitions",
        params=params,
        limit=limit,
    )
    normalized = [normalize_position(item) for item in positions]
    return {"positions": normalized, "total": len(normalized)}


def search_policy_content(
    api_base_url: str,
    access_token: str,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if query:
        params["search"] = query
    items = _paginate(
        api_base_url,
        access_token,
        "/learningCatalogItems",
        params=params,
        limit=limit,
    )
    normalized: list[dict[str, Any]] = []
    for item in items:
        normalized.append(
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("descriptor") or item.get("title") or item.get("id") or ""),
                "type": str(item.get("type") or "learning_catalog_item"),
                "status": str(item.get("status") or ""),
            }
        )
    return normalized


def get_policy_content_text(
    api_base_url: str,
    access_token: str,
    content_id: str,
) -> tuple[str, str, str | None]:
    """Return (title, plain_text_body, updated_at)."""
    cid = quote(str(content_id), safe="")
    data = _request("GET", api_base_url, access_token, f"/learningCatalogItems/{cid}")
    item = data.get("learningCatalogItem") if isinstance(data.get("learningCatalogItem"), dict) else data
    if not isinstance(item, dict):
        item = data
    title = str(item.get("descriptor") or item.get("title") or content_id)
    description = str(item.get("description") or item.get("summary") or "")
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    body = str(content.get("text") or content.get("value") or description or "")
    updated_at = item.get("lastUpdated") or item.get("updatedAt")
    return title, body.strip() or f"(empty Workday policy content {content_id})", (
        str(updated_at) if updated_at else None
    )
