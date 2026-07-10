"""Apollo.io agent tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.apollo_api import (
    ApolloAPIError,
    add_contacts_to_sequence,
    apollo_connection_auth_status,
    bulk_enrich_people,
    create_contact,
    create_label,
    create_task,
    delete_contact,
    get_contact,
    list_labels,
    remove_contacts_from_sequence,
    resolve_apollo_connector,
    search_organizations,
    search_people,
    subscribe_intent_signals,
    update_contact,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

_QUERY_KEYS = (
    "q",
    "query",
    "page",
    "per_page",
    "page_size",
    "limit",
    "person_titles",
    "person_locations",
    "organization_locations",
    "q_organization_domains_list",
    "organization_num_employees_ranges",
)

_RESERVED = frozenset(
    {
        "connector_id",
        "connectorId",
        "contact_id",
        "contactId",
        "sequence_id",
        "sequenceId",
        "contact_ids",
        "contactIds",
        "email_account_id",
        "emailAccountId",
        "details",
        "payload",
        "sequence_ids",
        "sequenceIds",
        "mode",
        "name",
        "modality",
    }
)


def _handle_error(exc: ApolloAPIError) -> Exception:
    message = str(exc)
    details = exc.details if isinstance(exc.details, dict) else {"raw": exc.details}
    if exc.status_code == 429:
        return ToolRateLimitedError(message, details=details if isinstance(details, dict) else None)
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(message, details=details if isinstance(details, dict) else None)
    return ToolValidationError(
        message,
        details=details if isinstance(details, dict) else {"raw": exc.details},
    )


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, dict[str, str]]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, headers = resolve_apollo_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "apollo", "apollo", cid)
    return cid, headers


def _search_params(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _QUERY_KEYS:
        if params.get(key) is not None:
            out[key] = params[key]
    payload = params.get("payload")
    if isinstance(payload, dict):
        out.update(payload)
    return out


def _body_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED and v is not None}


def _exec_people_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    try:
        data = search_people(headers, params=_search_params(params))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.people.search", connector_id=cid, data=data)


def _exec_organizations_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    try:
        data = search_organizations(headers, params=_search_params(params))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.organizations.search", connector_id=cid, data=data)


def _exec_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("id")
    if not contact_id:
        raise ToolValidationError("apollo.contacts.get requires contact_id")
    try:
        data = get_contact(headers, str(contact_id))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.contacts.get", connector_id=cid, data=data)


def _exec_lists_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    try:
        data = list_labels(headers)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.lists.list", connector_id=cid, data=data)


def _exec_lists_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    name = params.get("name") or params.get("list_name")
    if not name and isinstance(params.get("payload"), dict):
        name = params["payload"].get("name")
    if not name:
        raise ToolValidationError("apollo.lists.create requires name")
    modality = params.get("modality") or "contacts"
    try:
        data = create_label(headers, name=str(name), modality=str(modality))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.lists.create", connector_id=cid, data=data)


def _exec_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    body = _body_params(params)
    if not body:
        raise ToolValidationError("apollo.contacts.create requires contact fields")
    try:
        data = create_contact(headers, payload=body)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.contacts.create", connector_id=cid, data=data)


def _exec_sequences_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    sequence_id = params.get("sequence_id") or params.get("campaign_id")
    contact_ids = params.get("contact_ids") or params.get("ids")
    if not sequence_id or not isinstance(contact_ids, list):
        raise ToolValidationError("apollo.sequences.add requires sequence_id and contact_ids[]")
    try:
        data = add_contacts_to_sequence(
            headers,
            sequence_id=str(sequence_id),
            contact_ids=[str(x) for x in contact_ids],
            email_account_id=str(params["email_account_id"]) if params.get("email_account_id") else None,
        )
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.sequences.add", connector_id=cid, data=data)


def _exec_enrichment_bulk(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    details = params.get("details")
    if not isinstance(details, list):
        raise ToolValidationError("apollo.enrichment.bulk requires details[]")
    try:
        data = bulk_enrich_people(headers, details=details)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.enrichment.bulk", connector_id=cid, data=data)


def _exec_tasks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    body = _body_params(params)
    if not body:
        raise ToolValidationError("apollo.tasks.create requires task fields")
    try:
        data = create_task(headers, payload=body)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.tasks.create", connector_id=cid, data=data)


def _exec_signals_subscribe(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    body = _body_params(params)
    if not body:
        raise ToolValidationError("apollo.signals.subscribe requires signal filters")
    try:
        data = subscribe_intent_signals(headers, payload=body)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.signals.subscribe", connector_id=cid, data=data)


def _exec_contacts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("id")
    body = _body_params(params)
    if not contact_id:
        raise ToolValidationError("apollo.contacts.update requires contact_id")
    if not body:
        raise ToolValidationError("apollo.contacts.update requires contact fields")
    try:
        data = update_contact(headers, str(contact_id), payload=body)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.contacts.update", connector_id=cid, data=data)


def _exec_contacts_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("id")
    if not contact_id:
        raise ToolValidationError("apollo.contacts.delete requires contact_id")
    try:
        data = delete_contact(headers, str(contact_id))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.contacts.delete", connector_id=cid, data=data)


def _exec_sequences_remove(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    sequence_id = params.get("sequence_id") or params.get("campaign_id")
    sequence_ids = params.get("sequence_ids") or params.get("campaign_ids")
    contact_ids = params.get("contact_ids") or params.get("ids")
    if sequence_id and not sequence_ids:
        sequence_ids = [sequence_id]
    if not isinstance(sequence_ids, list) or not isinstance(contact_ids, list):
        raise ToolValidationError("apollo.sequences.remove requires sequence_id(s) and contact_ids[]")
    mode = str(params.get("mode") or "remove")
    try:
        data = remove_contacts_from_sequence(
            headers,
            sequence_ids=[str(x) for x in sequence_ids],
            contact_ids=[str(x) for x in contact_ids],
            mode=mode,
        )
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="apollo.sequences.remove", connector_id=cid, data=data)


APOLLO_TOOL_EXECUTORS: dict[str, Any] = {
    "apollo.people.search": _exec_people_search,
    "apollo.organizations.search": _exec_organizations_search,
    "apollo.contacts.get": _exec_contacts_get,
    "apollo.lists.list": _exec_lists_list,
    "apollo.contacts.create": _exec_contacts_create,
    "apollo.lists.create": _exec_lists_create,
    "apollo.sequences.add": _exec_sequences_add,
    "apollo.enrichment.bulk": _exec_enrichment_bulk,
    "apollo.tasks.create": _exec_tasks_create,
    "apollo.signals.subscribe": _exec_signals_subscribe,
    "apollo.contacts.update": _exec_contacts_update,
    "apollo.contacts.delete": _exec_contacts_delete,
    "apollo.sequences.remove": _exec_sequences_remove,
}
