"""Salesforce REST API client (STA-31 / v2).

v1: leads.get/update, opportunities.create/update_stage, accounts.get, tasks.create
v2: leads.create/search, opportunities.get/update, accounts.create/update
"""
from __future__ import annotations

import time
from typing import Any

import httpx

DEFAULT_API_VERSION = "v59.0"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class SalesforceAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _api_base(instance_url: str, api_version: str = DEFAULT_API_VERSION) -> str:
    return f"{instance_url.rstrip('/')}/services/data/{api_version}"


def _request(
    method: str,
    instance_url: str,
    access_token: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    url = f"{_api_base(instance_url, api_version)}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, json=json_body, params=params)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise SalesforceAPIError(
                    f"Salesforce API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()
        except SalesforceAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise SalesforceAPIError("Salesforce API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise SalesforceAPIError(str(exc)) from exc
    raise SalesforceAPIError(str(last_error or "Salesforce request failed"))


def get_lead(
    instance_url: str,
    access_token: str,
    lead_id: str,
    *,
    fields: list[str] | None = None,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    return _request(
        "GET",
        instance_url,
        access_token,
        f"/sobjects/Lead/{lead_id}",
        params=params or None,
        api_version=api_version,
    )


def update_lead(
    instance_url: str,
    access_token: str,
    lead_id: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "PATCH",
        instance_url,
        access_token,
        f"/sobjects/Lead/{lead_id}",
        json_body=fields,
        api_version=api_version,
    )


def get_account(
    instance_url: str,
    access_token: str,
    account_id: str,
    *,
    fields: list[str] | None = None,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    return _request(
        "GET",
        instance_url,
        access_token,
        f"/sobjects/Account/{account_id}",
        params=params or None,
        api_version=api_version,
    )


def create_opportunity(
    instance_url: str,
    access_token: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "POST",
        instance_url,
        access_token,
        "/sobjects/Opportunity",
        json_body=fields,
        api_version=api_version,
    )


def update_opportunity_stage(
    instance_url: str,
    access_token: str,
    opportunity_id: str,
    stage_name: str,
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "PATCH",
        instance_url,
        access_token,
        f"/sobjects/Opportunity/{opportunity_id}",
        json_body={"StageName": stage_name},
        api_version=api_version,
    )


def _soql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def query_soql(
    instance_url: str,
    access_token: str,
    soql: str,
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "GET",
        instance_url,
        access_token,
        "/query",
        params={"q": soql},
        api_version=api_version,
    )


def create_lead(
    instance_url: str,
    access_token: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "POST",
        instance_url,
        access_token,
        "/sobjects/Lead",
        json_body=fields,
        api_version=api_version,
    )


def search_leads(
    instance_url: str,
    access_token: str,
    *,
    soql: str | None = None,
    email: str | None = None,
    company: str | None = None,
    status: str | None = None,
    limit: int = 25,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    if soql:
        query = soql.strip()
    else:
        clauses: list[str] = []
        if email:
            clauses.append(f"Email = '{_soql_escape(str(email))}'")
        if company:
            clauses.append(f"Company = '{_soql_escape(str(company))}'")
        if status:
            clauses.append(f"Status = '{_soql_escape(str(status))}'")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        lim = max(1, min(int(limit), 200))
        query = f"SELECT Id, FirstName, LastName, Email, Company, Status FROM Lead{where} LIMIT {lim}"
    return query_soql(instance_url, access_token, query, api_version=api_version)


def get_opportunity(
    instance_url: str,
    access_token: str,
    opportunity_id: str,
    *,
    fields: list[str] | None = None,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    return _request(
        "GET",
        instance_url,
        access_token,
        f"/sobjects/Opportunity/{opportunity_id}",
        params=params or None,
        api_version=api_version,
    )


def update_opportunity(
    instance_url: str,
    access_token: str,
    opportunity_id: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "PATCH",
        instance_url,
        access_token,
        f"/sobjects/Opportunity/{opportunity_id}",
        json_body=fields,
        api_version=api_version,
    )


def create_account(
    instance_url: str,
    access_token: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "POST",
        instance_url,
        access_token,
        "/sobjects/Account",
        json_body=fields,
        api_version=api_version,
    )


def update_account(
    instance_url: str,
    access_token: str,
    account_id: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "PATCH",
        instance_url,
        access_token,
        f"/sobjects/Account/{account_id}",
        json_body=fields,
        api_version=api_version,
    )


def create_task(
    instance_url: str,
    access_token: str,
    fields: dict[str, Any],
    *,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    return _request(
        "POST",
        instance_url,
        access_token,
        "/sobjects/Task",
        json_body=fields,
        api_version=api_version,
    )
