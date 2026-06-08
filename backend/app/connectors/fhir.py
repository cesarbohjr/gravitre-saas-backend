"""FHIR R4 read client — sandbox + customer EHR endpoints (STA-113)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

FHIR_SANDBOX_BASE_URL = "https://hapi.fhir.org/baseR4"
TIMEOUT_SEC = 30.0


class FhirAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_fhir_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, str | None]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "fhir", environment_name=environment_name)
    if not conn:
        raise FhirAPIError("No active FHIR connector found for org")
    cid = str(conn["id"])
    config = conn.get("config") or {}
    base_url = (config.get("base_url") or config.get("baseUrl") or FHIR_SANDBOX_BASE_URL).strip().rstrip("/")
    token = get_decrypted_secret(client, cid, "bearer_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    return cid, base_url, token.strip() if token else None


def _request(
    method: str,
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{base_url}/{path.lstrip('/')}"
    headers = {"Accept": "application/fhir+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, params=params)
    if response.status_code >= 400:
        raise FhirAPIError(
            f"FHIR API {response.status_code}",
            status_code=response.status_code,
            details=response.text[:500],
        )
    if not response.text:
        return {}
    return response.json()


def get_patient(base_url: str, patient_id: str, *, token: str | None = None) -> dict[str, Any]:
    return _request("GET", base_url, f"Patient/{patient_id}", token=token)


def search_patients(
    base_url: str,
    *,
    token: str | None = None,
    name: str | None = None,
    birthdate: str | None = None,
    identifier: str | None = None,
    count: int = 10,
) -> dict[str, Any]:
    params: dict[str, Any] = {"_count": max(1, min(count, 50))}
    if name:
        params["name"] = name
    if birthdate:
        params["birthdate"] = birthdate
    if identifier:
        params["identifier"] = identifier
    return _request("GET", base_url, "Patient", token=token, params=params)


def search_appointments(
    base_url: str,
    *,
    token: str | None = None,
    patient_id: str | None = None,
    date: str | None = None,
    status: str | None = None,
    count: int = 10,
) -> dict[str, Any]:
    params: dict[str, Any] = {"_count": max(1, min(count, 50))}
    if patient_id:
        params["patient"] = patient_id
    if date:
        params["date"] = date
    if status:
        params["status"] = status
    return _request("GET", base_url, "Appointment", token=token, params=params)
