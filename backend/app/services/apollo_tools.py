"""Apollo.io agent tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.apollo_api import (
    ApolloAPIError,
    add_contacts_to_sequence,
    add_entity_ids_to_label_names,
    apollo_connection_auth_status,
    bulk_enrich_people,
    create_contact,
    create_label,
    create_task,
    delete_contact,
    enrich_organization,
    get_contact,
    is_apollo_plan_limit_error,
    list_labels,
    match_person,
    remove_contacts_from_sequence,
    resolve_apollo_connector,
    search_contacts,
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
    ToolPermissionDeniedError,
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
        "entity_ids",
        "entityIds",
        "label_names",
        "labelNames",
        "list_name",
        "listName",
        "list_names",
        "listNames",
        "contact_label_ids",
        "contactLabelIds",
        "page",
        "per_page",
        "page_size",
        "limit",
        "q_keywords",
        "q",
        "query",
    }
)


def _handle_error(exc: ApolloAPIError) -> Exception:
    message = str(exc)
    details = exc.details if isinstance(exc.details, dict) else {"raw": exc.details}
    if exc.status_code == 429:
        return ToolRateLimitedError(message, details=details if isinstance(details, dict) else None)
    if is_apollo_plan_limit_error(exc):
        return ToolPermissionDeniedError(
            message,
            details={**(details if isinstance(details, dict) else {"raw": exc.details}), "reason": "apollo_plan_limit"},
        )
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


def _emit_apollo_pack_notification(
    ctx: ToolContext,
    *,
    title: str,
    body: str,
    result_url: str | None,
    action: str,
) -> None:
    try:
        from app.services.intelligence_pack_tools import emit_pack_source_notification

        emit_pack_source_notification(
            ctx,
            title=title,
            body=body,
            result_url=result_url,
            action=action,
        )
    except Exception:  # noqa: BLE001
        pass


def _with_result_url(data: Any, result_url: str | None) -> dict[str, Any]:
    if isinstance(data, dict):
        payload = dict(data)
        if result_url:
            payload["result_url"] = result_url
        return payload
    return {"data": data, "result_url": result_url}


def _stamp_membership_ids(payload: dict[str, Any], rows: list[Any] | None) -> dict[str, Any]:
    """Stamp entity_ids / primary_contact_id for workflow from_step → lists.add wiring."""
    ids: list[str] = []
    primary_email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or row.get("contact_id") or row.get("person_id") or "").strip()
        if cid and cid not in ids:
            ids.append(cid)
        if not primary_email:
            email = row.get("email")
            if not email and isinstance(row.get("contact_emails"), list) and row["contact_emails"]:
                first = row["contact_emails"][0]
                email = first.get("email") if isinstance(first, dict) else first
            if email and str(email).strip():
                primary_email = str(email).strip()
                first_name = str(row.get("first_name") or row.get("firstname") or "").strip() or None
                last_name = str(row.get("last_name") or row.get("lastname") or "").strip() or None
    if ids:
        payload["entity_ids"] = ids
        payload["contact_ids"] = ids
        payload["primary_contact_id"] = ids[0]
    if primary_email:
        payload["primary_email"] = primary_email
        props: dict[str, Any] = {"email": primary_email}
        if first_name:
            props["firstname"] = first_name
        if last_name:
            props["lastname"] = last_name
        payload["hubspot_contact_properties"] = props
    return payload


def _exec_people_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    try:
        data = search_people(headers, params=_search_params(params))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    result_url = "https://app.apollo.io/#/people"
    payload = _with_result_url(data, result_url)
    people = payload.get("people") or payload.get("contacts") or []
    if not isinstance(people, list):
        people = []
    count = len(people)
    payload = _stamp_membership_ids(payload, people)
    _emit_apollo_pack_notification(
        ctx,
        title="Apollo people search",
        body=f"Found {count} contact(s)",
        result_url=result_url,
        action="apollo.people.search",
    )
    return NormalizedResult(success=True, action="apollo.people.search", connector_id=cid, data=payload)


def _exec_organizations_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    try:
        data = search_organizations(headers, params=_search_params(params))
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    result_url = "https://app.apollo.io/#/companies"
    payload = _with_result_url(data, result_url)
    orgs = payload.get("organizations") or payload.get("accounts") or []
    count = len(orgs) if isinstance(orgs, list) else 0
    _emit_apollo_pack_notification(
        ctx,
        title="Apollo organizations search",
        body=f"Found {count} organization(s)",
        result_url=result_url,
        action="apollo.organizations.search",
    )
    return NormalizedResult(success=True, action="apollo.organizations.search", connector_id=cid, data=payload)


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


def _label_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("labels", "label", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict) and key == "label":
            return [value]
    return []


def _resolve_contact_label_ids(headers: dict[str, str], params: dict[str, Any]) -> list[str]:
    """Resolve contact_label_ids from explicit ids and/or list/label names."""
    ids: list[str] = []
    raw_ids = params.get("contact_label_ids") or params.get("contactLabelIds")
    if isinstance(raw_ids, str) and raw_ids.strip():
        ids.append(raw_ids.strip())
    elif isinstance(raw_ids, list):
        ids.extend(str(x).strip() for x in raw_ids if str(x).strip())

    names: list[str] = []
    for key in ("label_names", "labelNames", "list_names", "listNames"):
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            names.append(raw.strip())
        elif isinstance(raw, list):
            names.extend(str(x).strip() for x in raw if str(x).strip())
    single = params.get("list_name") or params.get("listName") or params.get("name")
    if isinstance(single, str) and single.strip():
        names.append(single.strip())

    if not names:
        return ids

    try:
        labels_payload = list_labels(headers)
    except ApolloAPIError:
        return ids
    labels = _label_rows(labels_payload)
    wanted = {n.casefold() for n in names}
    for row in labels:
        row_name = str(row.get("name") or "").strip()
        if row_name.casefold() not in wanted:
            continue
        label_id = row.get("id") or row.get("_id")
        if label_id:
            ids.append(str(label_id))
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _exec_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    body: dict[str, Any] = {}
    payload = params.get("payload")
    if isinstance(payload, dict):
        body.update(payload)

    label_ids = _resolve_contact_label_ids(headers, params)
    if label_ids:
        body["contact_label_ids"] = label_ids

    for key in ("page", "per_page", "q_keywords", "sort_by_field", "sort_ascending"):
        if params.get(key) is not None and key not in body:
            body[key] = params[key]
    if params.get("page_size") is not None and "per_page" not in body:
        body["per_page"] = params["page_size"]
    if params.get("limit") is not None and "per_page" not in body:
        body["per_page"] = params["limit"]
    q = params.get("q") or params.get("query")
    if q is not None and "q_keywords" not in body:
        body["q_keywords"] = q

    try:
        data = search_contacts(headers, payload=body)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    contacts = data.get("contacts") if isinstance(data, dict) else None
    if not isinstance(contacts, list):
        contacts = []
    count = len(contacts)
    result_url = "https://app.apollo.io/#/contacts"
    payload_out = _with_result_url(data, result_url)
    if isinstance(payload_out, dict):
        payload_out["contact_count"] = count
        if label_ids:
            payload_out["contact_label_ids"] = label_ids
        payload_out = _stamp_membership_ids(payload_out, contacts)
    _emit_apollo_pack_notification(
        ctx,
        title="Apollo contacts search",
        body=f"Found {count} contact(s)",
        result_url=result_url,
        action="apollo.contacts.search",
    )
    return NormalizedResult(
        success=True,
        action="apollo.contacts.search",
        connector_id=cid,
        data=payload_out,
    )


def _exec_lists_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, headers = _session(ctx, params)
    entity_ids = params.get("entity_ids") or params.get("contact_ids") or params.get("ids")
    if isinstance(entity_ids, str) and entity_ids.strip():
        entity_ids = [entity_ids.strip()]
    if not isinstance(entity_ids, list) or not entity_ids:
        raise ToolValidationError("apollo.lists.add requires entity_ids[] (or contact_ids[])")

    label_names = params.get("label_names") or params.get("list_names")
    if not label_names:
        single = params.get("list_name") or params.get("name") or params.get("label_name")
        if single:
            label_names = [single]
    if isinstance(label_names, str) and label_names.strip():
        label_names = [label_names.strip()]
    if not isinstance(label_names, list) or not label_names:
        raise ToolValidationError("apollo.lists.add requires label_names[] (or list_name)")

    modality = str(params.get("modality") or "contacts")
    try:
        data = add_entity_ids_to_label_names(
            headers,
            entity_ids=[str(x) for x in entity_ids],
            label_names=[str(x) for x in label_names],
            modality=modality,
        )
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc

    from app.services.connector_output_mappers.apollo import resolve_list_result_url

    result_url = resolve_list_result_url(data if isinstance(data, dict) else {})
    if not result_url:
        result_url = "https://app.apollo.io/#/contacts"
    payload = _with_result_url(data, result_url)
    added = [str(x).strip() for x in entity_ids if str(x).strip()]
    # Membership proof for list-populate honesty (count > 0, not create-step alone).
    payload["entity_ids"] = added
    payload["added_count"] = len(added)
    payload["contact_count"] = len(added)
    names_joined = ", ".join(str(n) for n in label_names[:3])
    _emit_apollo_pack_notification(
        ctx,
        title=f"Apollo list membership: {names_joined}",
        body=f"Added {len(added)} contact(s) to {len(label_names)} list(s)",
        result_url=result_url,
        action="apollo.lists.add",
    )
    return NormalizedResult(success=True, action="apollo.lists.add", connector_id=cid, data=payload)


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
    from app.services.connector_output_mappers.apollo import resolve_list_result_url

    result_url = resolve_list_result_url(data if isinstance(data, dict) else {"label": data})
    payload = _with_result_url(data, result_url)
    if isinstance(payload, dict) and result_url and "list_id" not in payload:
        label = payload.get("label") if isinstance(payload.get("label"), dict) else payload
        if isinstance(label, dict) and (label.get("id") or label.get("_id")):
            payload["list_id"] = str(label.get("id") or label.get("_id"))
    already = bool(isinstance(payload, dict) and payload.get("already_existed"))
    if already:
        _emit_apollo_pack_notification(
            ctx,
            title=f"Apollo list already exists: {name}",
            body=f"Found existing {modality} list — no new list created; contacts not added",
            result_url=result_url,
            action="apollo.lists.create",
        )
    else:
        _emit_apollo_pack_notification(
            ctx,
            title=f"Apollo list created: {name}",
            body=f"Created {modality} list",
            result_url=result_url,
            action="apollo.lists.create",
        )
    return NormalizedResult(success=True, action="apollo.lists.create", connector_id=cid, data=payload)


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


def _exec_people_match(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    """Single-person enrichment (POST /people/match) — Batch 1 expansion."""
    cid, headers = _session(ctx, params)
    payload = params.get("payload") if isinstance(params.get("payload"), dict) else None
    if payload is None:
        payload = {
            k: v
            for k, v in params.items()
            if k
            in {
                "email",
                "first_name",
                "last_name",
                "name",
                "organization_name",
                "domain",
                "linkedin_url",
                "id",
            }
            and v not in (None, "")
        }
    if not payload:
        raise ToolValidationError(
            "apollo.people.match requires email and/or name+domain (or payload{})"
        )
    try:
        data = match_person(headers, payload=payload)
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    person = data.get("person") if isinstance(data, dict) else None
    person_id = person.get("id") if isinstance(person, dict) else None
    result_url = (
        f"https://app.apollo.io/#/people/{person_id}" if person_id else "https://app.apollo.io/#/people"
    )
    return NormalizedResult(
        success=True,
        action="apollo.people.match",
        connector_id=cid,
        data={
            **(data if isinstance(data, dict) else {"raw": data}),
            "result_url": result_url,
            "summary": (
                f"Matched person {person.get('name') or person_id}"
                if isinstance(person, dict)
                else "Apollo people.match completed"
            ),
        },
    )


def _exec_organizations_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    """Single-org enrichment (GET /organizations/enrich) — Batch 1 expansion."""
    cid, headers = _session(ctx, params)
    domain = str(params.get("domain") or params.get("organization_domain") or "").strip() or None
    name = str(params.get("name") or params.get("organization_name") or "").strip() or None
    linkedin_url = str(params.get("linkedin_url") or "").strip() or None
    website_url = str(params.get("website_url") or params.get("website") or "").strip() or None
    try:
        data = enrich_organization(
            headers,
            domain=domain,
            name=name,
            linkedin_url=linkedin_url,
            website_url=website_url,
        )
    except ApolloAPIError as exc:
        raise _handle_error(exc) from exc
    org = data.get("organization") if isinstance(data, dict) else None
    org_id = org.get("id") if isinstance(org, dict) else None
    result_url = (
        f"https://app.apollo.io/#/organizations/{org_id}"
        if org_id
        else "https://app.apollo.io/#/companies"
    )
    return NormalizedResult(
        success=True,
        action="apollo.organizations.enrich",
        connector_id=cid,
        data={
            **(data if isinstance(data, dict) else {"raw": data}),
            "result_url": result_url,
            "summary": (
                f"Enriched org {org.get('name') or org_id}"
                if isinstance(org, dict)
                else "Apollo organizations.enrich completed"
            ),
        },
    )


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


def probe_apollo_discovery_capabilities(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Any,
    *,
    environment_name: str | None = None,
) -> dict[str, Any]:
    """Lightweight capability probe for BYO search-plan labeling (not an executor).

    Calls the same HTTP search routes used by discovery tools so install/setup can
    warn on free-plan 403 before a workflow fails mid-run. Does not change
    apollo.people.search / apollo.organizations.search executors.
    """
    from app.connectors.apollo_discovery_capability import (
        APOLLO_DISCOVERY_CAPABILITY_NOTE,
        APOLLO_DISCOVERY_REQUIREMENT_NOTE,
        APOLLO_DISCOVERY_REQUIRES,
        APOLLO_DISCOVERY_USER_MESSAGE,
        is_apollo_discovery_plan_limit_text,
    )

    base: dict[str, Any] = {
        "vendor": "apollo",
        "discoveryRequires": APOLLO_DISCOVERY_REQUIRES,
        "requirementNote": APOLLO_DISCOVERY_REQUIREMENT_NOTE,
        "userMessage": APOLLO_DISCOVERY_USER_MESSAGE,
        "capabilityNote": APOLLO_DISCOVERY_CAPABILITY_NOTE,
        "searchPeople": None,
        "searchCompanies": None,
        "planLimited": False,
        "probed": False,
        "error": None,
    }
    try:
        _cid, headers = resolve_apollo_connector(
            client,
            org_id,
            connector_id,
            settings,
            environment_name=environment_name,
        )
    except ApolloAPIError as exc:
        base["error"] = str(exc)
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            base["planLimited"] = True
            base["searchPeople"] = False
            base["searchCompanies"] = False
            base["probed"] = True
        return base
    except Exception as exc:  # noqa: BLE001
        base["error"] = f"{exc.__class__.__name__}: {exc}"
        return base

    people_ok = False
    companies_ok = False
    plan_limited = False

    try:
        search_people(headers, params={"per_page": 1})
        people_ok = True
    except ApolloAPIError as exc:
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            plan_limited = True
            people_ok = False
        else:
            base["error"] = str(exc)

    try:
        search_organizations(headers, params={"per_page": 1})
        companies_ok = True
    except ApolloAPIError as exc:
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            plan_limited = True
            companies_ok = False
        elif not base.get("error"):
            base["error"] = str(exc)

    base.update(
        {
            "probed": True,
            "searchPeople": people_ok,
            "searchCompanies": companies_ok,
            "planLimited": plan_limited,
        }
    )
    if plan_limited:
        base["warning"] = APOLLO_DISCOVERY_USER_MESSAGE
    return base


APOLLO_TOOL_EXECUTORS: dict[str, Any] = {
    "apollo.people.search": _exec_people_search,
    "apollo.organizations.search": _exec_organizations_search,
    "apollo.contacts.get": _exec_contacts_get,
    "apollo.contacts.search": _exec_contacts_search,
    "apollo.lists.list": _exec_lists_list,
    "apollo.people.match": _exec_people_match,
    "apollo.organizations.enrich": _exec_organizations_enrich,
    "apollo.contacts.create": _exec_contacts_create,
    "apollo.lists.create": _exec_lists_create,
    "apollo.lists.add": _exec_lists_add,
    "apollo.sequences.add": _exec_sequences_add,
    "apollo.enrichment.bulk": _exec_enrichment_bulk,
    "apollo.tasks.create": _exec_tasks_create,
    "apollo.signals.subscribe": _exec_signals_subscribe,
    "apollo.contacts.update": _exec_contacts_update,
    "apollo.contacts.delete": _exec_contacts_delete,
    "apollo.sequences.remove": _exec_sequences_remove,
}
