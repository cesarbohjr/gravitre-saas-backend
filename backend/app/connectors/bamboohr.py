"""BambooHR REST API client (STA-87)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

TIMEOUT_SEC = 30.0


class BambooHRAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _api_base(subdomain: str) -> str:
    domain = subdomain.strip().lower().replace(".bamboohr.com", "")
    return f"https://api.bamboohr.com/api/gateway.php/{domain}/v1"


def resolve_bamboohr_credentials(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "bamboohr", environment_name=environment_name)
    if not conn:
        raise BambooHRAPIError("No active BambooHR connector found for org")
    cid = str(conn["id"])
    config = conn.get("config") or {}
    subdomain = (config.get("subdomain") or config.get("company_domain") or "").strip()
    if not subdomain:
        raise BambooHRAPIError("BambooHR subdomain missing on connector config")
    api_key = get_decrypted_secret(client, cid, "api_key", settings) or get_decrypted_secret(
        client, cid, "token", settings
    )
    if not api_key:
        raise BambooHRAPIError("BambooHR API key missing", status_code=401)
    return cid, subdomain, api_key.strip()


def _request(method: str, base: str, api_key: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, auth=(api_key, "x"), params=params)
    if response.status_code >= 400:
        raise BambooHRAPIError(f"BambooHR API {response.status_code}", status_code=response.status_code, details=response.text[:500])
    if not response.text:
        return {}
    return response.json()


def get_employee(base: str, api_key: str, employee_id: str) -> dict[str, Any]:
    return _request("GET", base, api_key, f"employees/{employee_id}")


def list_employees(base: str, api_key: str) -> dict[str, Any]:
    return _request("GET", base, api_key, "employees/directory")


def list_time_off_requests(base: str, api_key: str) -> dict[str, Any]:
    return _request("GET", base, api_key, "time_off/requests")


def run_report(base: str, api_key: str, report_id: str) -> dict[str, Any]:
    return _request("GET", base, api_key, f"reports/{report_id}")
