"""NetSuite REST Record API client (STA-57 / STA-58).

v1 read: customers.get, invoices.list/get, salesorders.get, items.get
v1 write (gated): journalentries.create draft, customers.update billing contact only
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0

DEFAULT_ITEM_TYPE = "inventoryItem"

_BILLING_CONTACT_FIELDS = frozenset(
    {
        "email",
        "phone",
        "altPhone",
        "fax",
        "contact",
        "defaultAddress",
        "addressbook",
        "addressbookList",
        "billAddressList",
        "billingAddress",
        "billingAddressList",
        "companyName",
        "entityId",
        "firstName",
        "lastName",
        "middleName",
        "salutation",
        "title",
    }
)


class NetSuiteAPIError(Exception):
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
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise NetSuiteAPIError(
                    f"NetSuite API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {}
            return response.json()
        except NetSuiteAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise NetSuiteAPIError("NetSuite API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise NetSuiteAPIError(str(exc)) from exc
    raise NetSuiteAPIError(str(last_error or "NetSuite request failed"))


def get_customer(
    api_base_url: str,
    access_token: str,
    customer_id: str,
) -> dict[str, Any]:
    return _request(
        "GET",
        api_base_url,
        access_token,
        f"/customer/{quote(str(customer_id), safe='')}",
    )


def list_invoices(
    api_base_url: str,
    access_token: str,
    *,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 1000))
    off = max(0, int(offset))
    return _request(
        "GET",
        api_base_url,
        access_token,
        "/invoice",
        params={"limit": lim, "offset": off},
    )


def get_invoice(
    api_base_url: str,
    access_token: str,
    invoice_id: str,
) -> dict[str, Any]:
    return _request(
        "GET",
        api_base_url,
        access_token,
        f"/invoice/{quote(str(invoice_id), safe='')}",
    )


def get_sales_order(
    api_base_url: str,
    access_token: str,
    sales_order_id: str,
) -> dict[str, Any]:
    return _request(
        "GET",
        api_base_url,
        access_token,
        f"/salesOrder/{quote(str(sales_order_id), safe='')}",
    )


def get_item(
    api_base_url: str,
    access_token: str,
    item_id: str,
    *,
    item_type: str = DEFAULT_ITEM_TYPE,
) -> dict[str, Any]:
    record_type = (item_type or DEFAULT_ITEM_TYPE).strip() or DEFAULT_ITEM_TYPE
    return _request(
        "GET",
        api_base_url,
        access_token,
        f"/{record_type}/{quote(str(item_id), safe='')}",
    )


def _filter_billing_contact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    filtered = {k: v for k, v in fields.items() if k in _BILLING_CONTACT_FIELDS}
    if not filtered:
        raise NetSuiteAPIError(
            "customers.update allows billing contact fields only",
            status_code=400,
        )
    return filtered


def update_customer_billing_contact(
    api_base_url: str,
    access_token: str,
    customer_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    payload = _filter_billing_contact_fields(fields)
    return _request(
        "PATCH",
        api_base_url,
        access_token,
        f"/customer/{quote(str(customer_id), safe='')}",
        json_body=payload,
    )


def create_journal_entry_draft(
    api_base_url: str,
    access_token: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    body = dict(entry)
    body.setdefault("approved", False)
    body.setdefault("draft", True)
    return _request(
        "POST",
        api_base_url,
        access_token,
        "/journalEntry",
        json_body=body,
    )


def create_sales_order(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise NetSuiteAPIError("create_sales_order requires payload", status_code=400)
    return _request(
        "POST",
        api_base_url,
        access_token,
        "/salesOrder",
        json_body=payload,
    )


def create_item_fulfillment(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise NetSuiteAPIError("create_item_fulfillment requires payload", status_code=400)
    return _request(
        "POST",
        api_base_url,
        access_token,
        "/itemFulfillment",
        json_body=payload,
    )
