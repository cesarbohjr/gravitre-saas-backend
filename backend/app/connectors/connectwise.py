"""ConnectWise Manage REST API client (service tickets + company inventory)."""
from __future__ import annotations

import base64
from typing import Any

import httpx

TIMEOUT_SEC = 45.0


class ConnectWiseAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _auth_header(*, company_id: str, public_key: str, private_key: str) -> str:
    raw = f"{company_id}+{public_key}:{private_key}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _base_url(site_url: str) -> str:
    host = str(site_url or "").strip().rstrip("/")
    if not host:
        raise ConnectWiseAPIError("ConnectWise site_url is required")
    if host.startswith("http://") or host.startswith("https://"):
        return f"{host}/v4_6_release/apis/3.0"
    return f"https://{host}/v4_6_release/apis/3.0"


def _request(
    *,
    site_url: str,
    company_id: str,
    public_key: str,
    private_key: str,
    client_id: str,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{_base_url(site_url)}{path}"
    headers = {
        "Authorization": _auth_header(company_id=company_id, public_key=public_key, private_key=private_key),
        "Content-Type": "application/json",
        "clientId": str(client_id or "").strip(),
    }
    if not headers["clientId"]:
        raise ConnectWiseAPIError("ConnectWise clientId is required")
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ConnectWiseAPIError(
            f"ConnectWise API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def list_companies(
    *,
    site_url: str,
    company_id: str,
    public_key: str,
    private_key: str,
    client_id: str,
    page_size: int = 25,
) -> list[dict[str, Any]]:
    data = _request(
        site_url=site_url,
        company_id=company_id,
        public_key=public_key,
        private_key=private_key,
        client_id=client_id,
        method="GET",
        path="/company/companies",
        params={"pageSize": min(max(int(page_size), 1), 100)},
    )
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, dict)]
    return []


def create_service_ticket(
    *,
    site_url: str,
    company_id: str,
    public_key: str,
    private_key: str,
    client_id: str,
    summary: str,
    board_id: int,
    company_record_id: int | None = None,
    description: str | None = None,
    priority_id: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": str(summary or "").strip(),
        "board": {"id": int(board_id)},
    }
    if company_record_id:
        body["company"] = {"id": int(company_record_id)}
    if description:
        body["initialDescription"] = str(description)
    if priority_id:
        body["priority"] = {"id": int(priority_id)}
    data = _request(
        site_url=site_url,
        company_id=company_id,
        public_key=public_key,
        private_key=private_key,
        client_id=client_id,
        method="POST",
        path="/service/tickets",
        json_body=body,
    )
    return data if isinstance(data, dict) else {"ticket": data}
