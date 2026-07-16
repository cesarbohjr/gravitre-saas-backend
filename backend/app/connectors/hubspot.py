"""HubSpot CRM API client.

v1 (STA-15): contacts.get/update, notes.create, deals.update_stage, sequences.enroll
v2: contacts.create/search, deals.get/create/update, lists.add_contact
"""
from __future__ import annotations

import time
from typing import Any

import httpx

HUBSPOT_API_BASE = "https://api.hubapi.com"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class HubSpotAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{HUBSPOT_API_BASE}{path}"
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
                raise HubSpotAPIError(
                    f"HubSpot API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {}
            return response.json()
        except HubSpotAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise HubSpotAPIError("HubSpot API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise HubSpotAPIError(str(exc)) from exc
    raise HubSpotAPIError(str(last_error or "HubSpot request failed"))


def get_contact(
    access_token: str,
    *,
    contact_id: str | None = None,
    email: str | None = None,
    properties: list[str] | None = None,
) -> dict[str, Any]:
    props = properties or ["email", "firstname", "lastname", "company", "lifecyclestage"]
    prop_query = ",".join(props)
    if contact_id:
        return _request(
            "GET",
            f"/crm/v3/objects/contacts/{contact_id}",
            access_token,
            params={"properties": prop_query},
        )
    if not email:
        raise HubSpotAPIError("contact_id or email is required")
    search = _request(
        "POST",
        "/crm/v3/objects/contacts/search",
        access_token,
        json_body={
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email.strip(),
                        }
                    ]
                }
            ],
            "properties": props,
            "limit": 1,
        },
    )
    results = search.get("results") or []
    if not results:
        raise HubSpotAPIError(f"No contact found for email", status_code=404)
    return results[0]


def update_contact(
    access_token: str,
    contact_id: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    if not contact_id:
        raise HubSpotAPIError("contact_id is required")
    if not properties:
        raise HubSpotAPIError("properties are required")
    return _request(
        "PATCH",
        f"/crm/v3/objects/contacts/{contact_id}",
        access_token,
        json_body={"properties": {str(k): str(v) for k, v in properties.items()}},
    )


def create_note(
    access_token: str,
    *,
    body: str,
    contact_id: str | None = None,
    deal_id: str | None = None,
) -> dict[str, Any]:
    if not body.strip():
        raise HubSpotAPIError("note body is required")
    if not contact_id and not deal_id:
        raise HubSpotAPIError("contact_id or deal_id is required for note association")
    note = _request(
        "POST",
        "/crm/v3/objects/notes",
        access_token,
        json_body={
            "properties": {
                "hs_note_body": body.strip(),
                "hs_timestamp": str(int(time.time() * 1000)),
            }
        },
    )
    note_id = note.get("id")
    if not note_id:
        return note
    if contact_id:
        _associate(access_token, from_type="notes", from_id=str(note_id), to_type="contacts", to_id=contact_id)
    if deal_id:
        _associate(access_token, from_type="notes", from_id=str(note_id), to_type="deals", to_id=deal_id)
    return note


def _associate(
    access_token: str,
    *,
    from_type: str,
    from_id: str,
    to_type: str,
    to_id: str,
) -> dict[str, Any]:
    return create_association(
        access_token,
        from_type=from_type,
        from_id=from_id,
        to_type=to_type,
        to_id=to_id,
    )


def create_association(
    access_token: str,
    *,
    from_type: str,
    from_id: str,
    to_type: str,
    to_id: str,
) -> dict[str, Any]:
    """Associate two CRM objects — PUT /crm/v4/objects/.../associations/default/..."""
    if not from_type or not from_id or not to_type or not to_id:
        raise HubSpotAPIError("from_type, from_id, to_type, and to_id are required")
    ft = str(from_type).strip().lower()
    tt = str(to_type).strip().lower()
    # Accept singular catalog names (contact) and HubSpot object plurals (contacts).
    aliases = {
        "contact": "contacts",
        "company": "companies",
        "deal": "deals",
        "ticket": "tickets",
        "note": "notes",
    }
    ft = aliases.get(ft, ft)
    tt = aliases.get(tt, tt)
    return _request(
        "PUT",
        f"/crm/v4/objects/{ft}/{from_id}/associations/default/{tt}/{to_id}",
        access_token,
    )


def update_deal_stage(
    access_token: str,
    deal_id: str,
    dealstage: str,
) -> dict[str, Any]:
    if not deal_id:
        raise HubSpotAPIError("deal_id is required")
    if not dealstage:
        raise HubSpotAPIError("dealstage is required")
    return _request(
        "PATCH",
        f"/crm/v3/objects/deals/{deal_id}",
        access_token,
        json_body={"properties": {"dealstage": dealstage}},
    )


def create_contact(access_token: str, properties: dict[str, Any]) -> dict[str, Any]:
    if not properties:
        raise HubSpotAPIError("properties are required")
    return _request(
        "POST",
        "/crm/v3/objects/contacts",
        access_token,
        json_body={"properties": {str(k): str(v) for k, v in properties.items()}},
    )


def search_contacts(
    access_token: str,
    *,
    filter_groups: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not filter_groups:
        raise HubSpotAPIError("filter_groups is required for contact search")
    lim = min(max(int(limit), 1), 100)
    props = properties or ["email", "firstname", "lastname", "company"]
    return _request(
        "POST",
        "/crm/v3/objects/contacts/search",
        access_token,
        json_body={
            "filterGroups": filter_groups,
            "properties": props,
            "limit": lim,
        },
    )


def list_contacts(
    access_token: str,
    *,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """List recent CRM contacts (no search filter required)."""
    lim = min(max(int(limit), 1), 100)
    props = properties or ["email", "firstname", "lastname", "company"]
    return _request(
        "GET",
        "/crm/v3/objects/contacts",
        access_token,
        params={"limit": lim, "properties": ",".join(props)},
    )


def get_deal(
    access_token: str,
    deal_id: str,
    *,
    properties: list[str] | None = None,
) -> dict[str, Any]:
    if not deal_id:
        raise HubSpotAPIError("deal_id is required")
    props = properties or ["dealname", "dealstage", "amount", "closedate", "pipeline"]
    prop_query = ",".join(props)
    return _request(
        "GET",
        f"/crm/v3/objects/deals/{deal_id}",
        access_token,
        params={"properties": prop_query},
    )


def create_deal(
    access_token: str,
    properties: dict[str, Any],
    *,
    contact_id: str | None = None,
) -> dict[str, Any]:
    if not properties:
        raise HubSpotAPIError("properties are required")
    deal = _request(
        "POST",
        "/crm/v3/objects/deals",
        access_token,
        json_body={"properties": {str(k): str(v) for k, v in properties.items()}},
    )
    deal_id = deal.get("id")
    if deal_id and contact_id:
        _associate(
            access_token,
            from_type="deals",
            from_id=str(deal_id),
            to_type="contacts",
            to_id=str(contact_id),
        )
    return deal


def update_deal(access_token: str, deal_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    if not deal_id:
        raise HubSpotAPIError("deal_id is required")
    if not properties:
        raise HubSpotAPIError("properties are required")
    return _request(
        "PATCH",
        f"/crm/v3/objects/deals/{deal_id}",
        access_token,
        json_body={"properties": {str(k): str(v) for k, v in properties.items()}},
    )


def delete_contact(access_token: str, contact_id: str) -> dict[str, Any]:
    if not contact_id:
        raise HubSpotAPIError("contact_id is required")
    return _request("DELETE", f"/crm/v3/objects/contacts/{contact_id}", access_token)


def delete_deal(access_token: str, deal_id: str) -> dict[str, Any]:
    if not deal_id:
        raise HubSpotAPIError("deal_id is required")
    return _request("DELETE", f"/crm/v3/objects/deals/{deal_id}", access_token)


def delete_note(access_token: str, note_id: str) -> dict[str, Any]:
    if not note_id:
        raise HubSpotAPIError("note_id is required")
    return _request("DELETE", f"/crm/v3/objects/notes/{note_id}", access_token)


def add_contact_to_list(access_token: str, list_id: str, contact_id: str) -> dict[str, Any]:
    if not list_id or not contact_id:
        raise HubSpotAPIError("list_id and contact_id are required")
    return _request(
        "PUT",
        f"/crm/v3/lists/{list_id}/memberships/add",
        access_token,
        json_body=[str(contact_id)],
    )


def create_list(
    access_token: str,
    name: str,
    *,
    object_type_id: str = "0-1",
    processing_type: str = "MANUAL",
) -> dict[str, Any]:
    """Create a HubSpot CRM list (contacts by default: objectTypeId 0-1)."""
    if not name or not str(name).strip():
        raise HubSpotAPIError("name is required")
    return _request(
        "POST",
        "/crm/v3/lists",
        access_token,
        json_body={
            "name": str(name).strip()[:100],
            "objectTypeId": str(object_type_id or "0-1"),
            "processingType": str(processing_type or "MANUAL"),
        },
    )


def search_crm_objects(
    access_token: str,
    object_type: str,
    *,
    properties: list[str],
    since_ms: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search CRM objects (e.g. notes, emails) optionally filtered by last modified."""
    if not object_type:
        raise HubSpotAPIError("object_type is required")
    lim = min(max(int(limit), 1), 100)
    body: dict[str, Any] = {
        "properties": properties,
        "limit": lim,
        "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
    }
    if since_ms is not None:
        body["filterGroups"] = [
            {
                "filters": [
                    {
                        "propertyName": "hs_lastmodifieddate",
                        "operator": "GTE",
                        "value": str(int(since_ms)),
                    }
                ]
            }
        ]
    data = _request(
        "POST",
        f"/crm/v3/objects/{object_type}/search",
        access_token,
        json_body=body,
    )
    return [dict(r) for r in (data.get("results") or []) if isinstance(r, dict)]


def list_notes_since(
    access_token: str,
    *,
    since_ms: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return search_crm_objects(
        access_token,
        "notes",
        properties=["hs_note_body", "hs_timestamp", "hs_lastmodifieddate"],
        since_ms=since_ms,
        limit=limit,
    )


def list_emails_since(
    access_token: str,
    *,
    since_ms: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return search_crm_objects(
        access_token,
        "emails",
        properties=["hs_email_subject", "hs_email_text", "hs_timestamp", "hs_lastmodifieddate"],
        since_ms=since_ms,
        limit=limit,
    )


def enroll_contact_in_sequence(
    access_token: str,
    *,
    contact_id: str,
    sequence_id: str,
    sender_email: str | None = None,
) -> dict[str, Any]:
    if not contact_id or not sequence_id:
        raise HubSpotAPIError("contact_id and sequence_id are required")
    body: dict[str, Any] = {
        "contactId": contact_id,
        "sequenceId": sequence_id,
    }
    if sender_email:
        body["senderEmail"] = sender_email.strip()
    return _request(
        "POST",
        "/automation/v4/sequences/enrollments",
        access_token,
        json_body=body,
    )


def search_companies(
    access_token: str,
    *,
    filter_groups: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not filter_groups:
        raise HubSpotAPIError("filter_groups is required for company search")
    lim = min(max(int(limit), 1), 100)
    props = properties or ["name", "domain", "city", "industry"]
    return _request(
        "POST",
        "/crm/v3/objects/companies/search",
        access_token,
        json_body={
            "filterGroups": filter_groups,
            "properties": props,
            "limit": lim,
        },
    )


def list_deal_pipelines(access_token: str) -> dict[str, Any]:
    return _request("GET", "/crm/v3/pipelines/deals", access_token)


def create_ticket(access_token: str, properties: dict[str, Any]) -> dict[str, Any]:
    if not properties:
        raise HubSpotAPIError("properties are required")
    return _request(
        "POST",
        "/crm/v3/objects/tickets",
        access_token,
        json_body={"properties": {str(k): str(v) for k, v in properties.items()}},
    )


def search_deals(
    access_token: str,
    *,
    filter_groups: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not filter_groups:
        raise HubSpotAPIError("filter_groups is required for deal search")
    lim = min(max(int(limit), 1), 100)
    props = properties or ["dealname", "dealstage", "amount", "closedate", "pipeline"]
    return _request(
        "POST",
        "/crm/v3/objects/deals/search",
        access_token,
        json_body={"filterGroups": filter_groups, "properties": props, "limit": lim},
    )


def list_deals(
    access_token: str,
    *,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    lim = min(max(int(limit), 1), 100)
    props = properties or ["dealname", "dealstage", "amount", "closedate", "pipeline"]
    return _request(
        "GET",
        "/crm/v3/objects/deals",
        access_token,
        params={"limit": lim, "properties": ",".join(props)},
    )


def get_company(
    access_token: str,
    *,
    company_id: str | None = None,
    domain: str | None = None,
    properties: list[str] | None = None,
) -> dict[str, Any]:
    props = properties or ["name", "domain", "city", "industry", "phone"]
    if company_id:
        return _request(
            "GET",
            f"/crm/v3/objects/companies/{company_id}",
            access_token,
            params={"properties": ",".join(props)},
        )
    if domain:
        search = search_companies(
            access_token,
            filter_groups=[
                {
                    "filters": [
                        {"propertyName": "domain", "operator": "EQ", "value": domain.strip()},
                    ]
                }
            ],
            properties=props,
            limit=1,
        )
        results = search.get("results") or []
        if not results:
            raise HubSpotAPIError("No company found for domain", status_code=404)
        return results[0]
    raise HubSpotAPIError("company_id or domain is required")


def search_tickets(
    access_token: str,
    *,
    filter_groups: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not filter_groups:
        raise HubSpotAPIError("filter_groups is required for ticket search")
    lim = min(max(int(limit), 1), 100)
    props = properties or ["subject", "content", "hs_pipeline_stage", "hs_ticket_priority"]
    return _request(
        "POST",
        "/crm/v3/objects/tickets/search",
        access_token,
        json_body={"filterGroups": filter_groups, "properties": props, "limit": lim},
    )
