"""QuickBooks Online API client (STA-34).

v1 read: invoices.list/get, payments.list, vendors.get
v2 read: customers.list/get/search, vendors.list, accounts.list, bills.list/get, companyinfo.get
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_MINOR_VERSION = "65"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class QuickBooksAPIError(Exception):
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
    query = dict(params or {})
    if "minorversion" not in query:
        query["minorversion"] = DEFAULT_MINOR_VERSION

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=query,
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
                raise QuickBooksAPIError(
                    f"QuickBooks API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {}
            return response.json()
        except QuickBooksAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise QuickBooksAPIError("QuickBooks API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise QuickBooksAPIError(str(exc)) from exc
    raise QuickBooksAPIError(str(last_error or "QuickBooks request failed"))


def _query(
    api_base_url: str,
    access_token: str,
    sql: str,
) -> dict[str, Any]:
    return _request(
        "GET",
        api_base_url,
        access_token,
        "/query",
        params={"query": sql},
    )


def _soql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _list_entity(
    api_base_url: str,
    access_token: str,
    entity: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    lim = max(1, min(int(max_results), 1000))
    pos = max(1, int(start_position))
    sql = f"select * from {entity} maxresults {lim} startposition {pos}"
    return _query(api_base_url, access_token, sql)


def _realm_from_api_base(api_base_url: str) -> str:
    return api_base_url.rstrip("/").split("/")[-1]


def list_invoices(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    lim = max(1, min(int(max_results), 1000))
    pos = max(1, int(start_position))
    sql = f"select * from Invoice maxresults {lim} startposition {pos}"
    return _query(api_base_url, access_token, sql)


def get_invoice(
    api_base_url: str,
    access_token: str,
    invoice_id: str,
) -> dict[str, Any]:
    return _request("GET", api_base_url, access_token, f"/invoice/{quote(str(invoice_id), safe='')}")


def list_payments(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    lim = max(1, min(int(max_results), 1000))
    pos = max(1, int(start_position))
    sql = f"select * from Payment maxresults {lim} startposition {pos}"
    return _query(api_base_url, access_token, sql)


def get_vendor(
    api_base_url: str,
    access_token: str,
    vendor_id: str,
) -> dict[str, Any]:
    return _request("GET", api_base_url, access_token, f"/vendor/{quote(str(vendor_id), safe='')}")


def list_customers(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    return _list_entity(
        api_base_url, access_token, "Customer", max_results=max_results, start_position=start_position
    )


def get_customer(
    api_base_url: str,
    access_token: str,
    customer_id: str,
) -> dict[str, Any]:
    return _request("GET", api_base_url, access_token, f"/customer/{quote(str(customer_id), safe='')}")


def search_customers(
    api_base_url: str,
    access_token: str,
    *,
    display_name: str | None = None,
    email: str | None = None,
    max_results: int = 25,
) -> dict[str, Any]:
    clauses: list[str] = []
    if email:
        clauses.append(f"PrimaryEmailAddr = '{_soql_escape(str(email))}'")
    if display_name:
        clauses.append(f"DisplayName LIKE '%{_soql_escape(str(display_name))}%'")
    if not clauses:
        raise QuickBooksAPIError(
            "search_customers requires display_name or email",
            status_code=400,
        )
    lim = max(1, min(int(max_results), 1000))
    where = " WHERE " + " AND ".join(clauses)
    sql = f"select * from Customer{where} maxresults {lim}"
    return _query(api_base_url, access_token, sql)


def list_vendors(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    return _list_entity(
        api_base_url, access_token, "Vendor", max_results=max_results, start_position=start_position
    )


def list_accounts(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    return _list_entity(
        api_base_url, access_token, "Account", max_results=max_results, start_position=start_position
    )


def list_bills(
    api_base_url: str,
    access_token: str,
    *,
    max_results: int = 25,
    start_position: int = 1,
) -> dict[str, Any]:
    return _list_entity(
        api_base_url, access_token, "Bill", max_results=max_results, start_position=start_position
    )


def get_bill(
    api_base_url: str,
    access_token: str,
    bill_id: str,
) -> dict[str, Any]:
    return _request("GET", api_base_url, access_token, f"/bill/{quote(str(bill_id), safe='')}")


def get_company_info(
    api_base_url: str,
    access_token: str,
) -> dict[str, Any]:
    realm_id = _realm_from_api_base(api_base_url)
    return _request(
        "GET",
        api_base_url,
        access_token,
        f"/companyinfo/{quote(realm_id, safe='')}",
    )


def create_invoice(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise QuickBooksAPIError("create_invoice requires payload", status_code=400)
    return _request("POST", api_base_url, access_token, "/invoice", json_body=payload)


def create_customer(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise QuickBooksAPIError("create_customer requires payload", status_code=400)
    return _request("POST", api_base_url, access_token, "/customer", json_body=payload)


def create_payment(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise QuickBooksAPIError("create_payment requires payload", status_code=400)
    return _request("POST", api_base_url, access_token, "/payment", json_body=payload)


def create_journal_entry(
    api_base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        raise QuickBooksAPIError("create_journal_entry requires payload", status_code=400)
    return _request("POST", api_base_url, access_token, "/journalentry", json_body=payload)
