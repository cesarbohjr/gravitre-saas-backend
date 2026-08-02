"""Clay agent tool executors."""
from __future__ import annotations

from typing import Any

from app.connectors.clay_api import (
    ClayAPIError,
    enrich_company,
    enrich_person,
    list_tables,
    pull_workflow_outputs,
    request_enrichment,
    resolve_clay_connector,
)
from app.connectors.hubspot import HubSpotAPIError, create_contact as hubspot_create_contact
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector
from app.connectors.salesforce import SalesforceAPIError, create_lead
from app.connectors.salesforce_oauth import ensure_salesforce_session
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: ClayAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, api_key, config = resolve_clay_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ClayAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "clay", "clay", cid)
    return cid, api_key, config


def _clay_record_to_crm_properties(record: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "email": "email",
        "first_name": "firstname",
        "firstname": "firstname",
        "last_name": "lastname",
        "lastname": "lastname",
        "company": "company",
        "title": "jobtitle",
        "job_title": "jobtitle",
        "phone": "phone",
        "linkedin_url": "linkedin",
        "linkedin": "linkedin",
        "website": "website",
        "domain": "website",
    }
    props: dict[str, Any] = {}
    for src, dest in mapping.items():
        value = record.get(src)
        if value not in (None, ""):
            props[dest] = value
    for key, value in record.items():
        if key.startswith("crm_") and value not in (None, ""):
            props[key.removeprefix("crm_")] = value
    return props


def _exec_tables_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, config = _session(ctx, params)
    data = list_tables(config)
    return NormalizedResult(success=True, action="clay.tables.list", connector_id=cid, data=data)


def _exec_people_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, _ = _session(ctx, params)
    email = str(params.get("email") or "").strip() or None
    linkedin_url = str(params.get("linkedin_url") or params.get("linkedinUrl") or "").strip() or None
    payload = params.get("payload") if isinstance(params.get("payload"), dict) else None
    try:
        data = enrich_person(api_key, email=email, linkedin_url=linkedin_url, payload=payload)
    except ClayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clay.people.enrich", connector_id=cid, data=data)


def _exec_companies_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, _ = _session(ctx, params)
    domain = str(params.get("domain") or "").strip() or None
    payload = params.get("payload") if isinstance(params.get("payload"), dict) else None
    try:
        data = enrich_company(api_key, domain=domain, payload=payload)
    except ClayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clay.companies.enrich", connector_id=cid, data=data)


def _normalize_records_param(params: dict[str, Any]) -> list[dict[str, Any]]:
    records = params.get("records")
    if isinstance(records, list) and records:
        return [dict(r) for r in records if isinstance(r, dict)]
    record = params.get("record") if isinstance(params.get("record"), dict) else None
    if record:
        return [dict(record)]
    if isinstance(params.get("payload"), dict):
        return [dict(params["payload"])]
    return []


def _exec_leads_push(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, config = _session(ctx, params)
    records = _normalize_records_param(params)
    if not records:
        payload = {
            k: v
            for k, v in params.items()
            if k
            not in {
                "connector_id",
                "connectorId",
                "table_id",
                "tableId",
                "webhook_url",
                "webhookUrl",
                "records",
                "record",
                "payload",
            }
        }
        if payload:
            records = [payload]
    if not records:
        raise ToolValidationError("clay.leads.push requires records, record, or lead fields")
    table_id = str(params.get("table_id") or params.get("tableId") or "").strip() or None
    webhook_url = str(params.get("webhook_url") or params.get("webhookUrl") or "").strip() or None
    try:
        data = request_enrichment(
            api_key,
            config,
            records=records,
            table_id=table_id,
            webhook_url=webhook_url,
        )
    except ClayAPIError as exc:
        raise _handle_error(exc) from exc
    # Echo records so clay.workflows.output.get / clay.crm.sync can from_step them.
    # Clay's pull_workflow_outputs only returns connector destinations, not row payloads.
    out = dict(data) if isinstance(data, dict) else {"result": data}
    out["records"] = records
    out["clay_records"] = records
    out["enriched_records"] = records
    out["record_count"] = len(records)
    return NormalizedResult(success=True, action="clay.leads.push", connector_id=cid, data=out)


def _exec_enrichments_request(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, config = _session(ctx, params)
    records = _normalize_records_param(params)
    if not records:
        raise ToolValidationError("clay.enrichments.request requires records or record")
    table_id = str(params.get("table_id") or params.get("tableId") or "").strip() or None
    try:
        data = request_enrichment(
            api_key,
            config,
            records=records,
            table_id=table_id,
        )
    except ClayAPIError as exc:
        raise _handle_error(exc) from exc
    out = dict(data) if isinstance(data, dict) else {"result": data}
    out["records"] = records
    out["record_count"] = len(records)
    return NormalizedResult(success=True, action="clay.enrichments.request", connector_id=cid, data=out)


def _exec_workflows_output_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, config = _session(ctx, params)
    data = pull_workflow_outputs(config)
    out = dict(data) if isinstance(data, dict) else {"result": data}
    # Prefer upstream records (from clay.leads.push). Clay config destinations rarely include rows.
    upstream_records = _normalize_records_param(params)
    config_records = out.get("records") if isinstance(out.get("records"), list) else []
    records = upstream_records or [r for r in config_records if isinstance(r, dict)]
    if records:
        out["records"] = records
        out["clay_records"] = records
        out["enriched_records"] = records
        out["record_count"] = len(records)
        out.setdefault("source", "upstream_records" if upstream_records else out.get("source"))
    return NormalizedResult(success=True, action="clay.workflows.output.get", connector_id=cid, data=out)


def _exec_crm_sync(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, config = _session(ctx, params)
    records = params.get("records")
    if not isinstance(records, list) or not records:
        record = params.get("record")
        records = [record] if isinstance(record, dict) else []
    if not records:
        raise ToolValidationError("clay.crm.sync requires records or record")

    crm = str(params.get("crm") or params.get("target") or config.get("crm_sync_target") or config.get("crmSyncTarget") or "hubspot").strip().lower()
    crm_connector_id = str(
        params.get("crm_connector_id")
        or params.get("crmConnectorId")
        or config.get("crm_connector_id")
        or config.get("crmConnectorId")
        or ""
    ).strip()
    if not crm_connector_id:
        raise ToolValidationError("clay.crm.sync requires crm_connector_id or connector config crm_connector_id")

    crm_row = get_connector(ctx.client, ctx.org_id, crm_connector_id, environment_name=ctx.environment_name)
    if not crm_row:
        raise ToolValidationError(f"CRM connector {crm_connector_id} not found")

    synced: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        properties = _clay_record_to_crm_properties(record)
        if not properties.get("email") and not properties.get("lastname"):
            errors.append({"record": record, "error": "email or lastname required for CRM sync"})
            continue
        try:
            if crm in {"hubspot", "hs"}:
                token, err = ensure_hubspot_access_token(
                    ctx.client, ctx.org_id, crm_connector_id, ctx.settings, environment_name=ctx.environment_name
                )
                if err or not token:
                    raise ToolAuthExpiredError(err or "HubSpot session expired")
                result = hubspot_create_contact(token, properties)
                synced.append({"crm": "hubspot", "result": result})
            elif crm in {"salesforce", "sfdc"}:
                token, instance_url, err = ensure_salesforce_session(
                    ctx.client, ctx.org_id, crm_connector_id, ctx.settings, environment_name=ctx.environment_name
                )
                if err or not token or not instance_url:
                    raise ToolAuthExpiredError(err or "Salesforce session expired")
                sf_props = {
                    "Email": properties.get("email"),
                    "FirstName": properties.get("firstname"),
                    "LastName": properties.get("lastname") or properties.get("email"),
                    "Company": properties.get("company"),
                    "Title": properties.get("jobtitle"),
                    "Phone": properties.get("phone"),
                    "Website": properties.get("website"),
                }
                sf_props = {k: v for k, v in sf_props.items() if v}
                result = create_lead(instance_url, token, sf_props)
                synced.append({"crm": "salesforce", "result": result})
            else:
                raise ToolValidationError(f"Unsupported CRM target: {crm}")
        except (HubSpotAPIError, SalesforceAPIError) as exc:
            errors.append({"record": record, "error": str(exc)})
        except ToolAuthExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            errors.append({"record": record, "error": str(exc)})

    contact_ids: list[str] = []
    for row in synced:
        if not isinstance(row, dict):
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        hid = str(result.get("id") or result.get("contactId") or "").strip()
        if hid and hid not in contact_ids:
            contact_ids.append(hid)
    return NormalizedResult(
        success=bool(synced) and not errors,
        action="clay.crm.sync",
        connector_id=cid,
        data={
            "synced": synced,
            "errors": errors,
            "crm": crm,
            "crm_connector_id": crm_connector_id,
            "contact_ids": contact_ids,
            "primary_contact_id": contact_ids[0] if contact_ids else None,
            "contact_id": contact_ids[0] if contact_ids else None,
            "added_count": len(contact_ids),
        },
    )


CLAY_TOOL_EXECUTORS: dict[str, Any] = {
    "clay.tables.list": _exec_tables_list,
    "clay.people.enrich": _exec_people_enrich,
    "clay.companies.enrich": _exec_companies_enrich,
    "clay.leads.push": _exec_leads_push,
    "clay.enrichments.request": _exec_enrichments_request,
    "clay.workflows.output.get": _exec_workflows_output_get,
    "clay.crm.sync": _exec_crm_sync,
}
