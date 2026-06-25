"""Unified tool invocation for agents and workflows (STA-10)."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.connectors.email import body_hash as _body_hash
from app.connectors.email import extract_to_domain
from app.connectors.email import send_email_smtp
from app.connectors.email import subject_hash as _subject_hash
from app.connectors.rate_limit import RateLimitError, enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.connectors.slack import (
    conversation_history,
    list_conversations,
    list_users,
    message_hash,
    send_slack_message,
)
from app.connectors.webhook import (
    ALLOWED_HEADER_NAMES as WEBHOOK_ALLOWED_HEADERS,
    build_headers,
    build_url,
    coerce_payload,
    parse_connector_config,
    payload_hash as _payload_hash,
    resolve_and_validate_host,
    sanitize_headers,
    send_webhook,
    validate_path,
)
from app.connectors.crypto import decrypt_secret
from app.connectors.hubspot import (
    HubSpotAPIError,
    add_contact_to_list,
    create_contact,
    create_deal,
    create_note,
    create_ticket,
    delete_contact,
    delete_deal,
    delete_note,
    enroll_contact_in_sequence,
    get_contact,
    get_deal,
    list_deal_pipelines,
    search_companies,
    search_contacts,
    update_contact,
    update_deal,
    update_deal_stage,
)
from app.connectors.salesforce import (
    SalesforceAPIError,
    create_account,
    create_lead,
    create_opportunity,
    create_task,
    get_account,
    get_lead,
    get_opportunity,
    search_leads,
    update_account,
    update_lead,
    update_opportunity,
    update_opportunity_stage,
)
from app.connectors.quickbooks import (
    QuickBooksAPIError,
    create_customer,
    create_invoice,
    create_journal_entry,
    create_payment,
    get_bill,
    get_company_info,
    get_customer,
    get_invoice,
    get_vendor,
    list_accounts,
    list_bills,
    list_customers,
    list_invoices,
    list_payments,
    list_vendors,
    search_customers,
)
from app.connectors.quickbooks_oauth import ensure_quickbooks_session
from app.connectors.stripe_api import (
    StripeAPIError,
    get_subscription,
    list_invoices,
    resolve_stripe_credentials,
)
from app.connectors.pagerduty import (
    PagerDutyAPIError,
    acknowledge_incident,
    add_incident_note,
    escalate_incident,
    fetch_current_user as fetch_pagerduty_user,
    get_incident,
    list_incident_notes,
    list_incidents,
    list_oncalls,
    list_services,
    reassign_incident,
    resolve_incident,
)
from app.connectors.pagerduty_oauth import ensure_pagerduty_session
from app.connectors.jira import (
    JiraAPIError,
    add_issue_comment,
    assign_issue,
    create_issue as jira_create_issue,
    get_issue,
    list_issue_transitions,
    list_projects,
    search_issues,
    search_users,
    transition_issue,
    update_issue,
)
from app.connectors.jira_oauth import ensure_jira_session
from app.connectors.salesforce_oauth import ensure_salesforce_session
from app.connectors.github_api import (
    GitHubAPIError,
    close_pull_request,
    create_issue,
    create_issue_comment,
    create_release,
    dispatch_workflow,
    get_issue,
    get_pull_request,
    get_repository,
    list_issues,
    list_pull_requests,
    merge_pull_request,
    request_pull_request_reviewer,
)
from app.connectors.google_calendar import (
    GoogleCalendarAPIError,
    create_event,
    default_window_iso,
    list_calendars,
    list_events,
    query_freebusy,
)
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.connectors.zendesk import (
    ZendeskAPIError,
    add_ticket_tags,
    close_ticket,
    create_ticket,
    get_ticket,
    get_user as zendesk_get_user,
    list_tickets,
    update_ticket,
)
from app.services.agent_tool_permissions import assert_agent_tool_permission
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolRateLimitedError,
    ToolValidationError,
)
from app.workflows.audit import write_audit_event
from app.workflows.constants import RESOURCE_TYPE_WORKFLOW_RUN

ToolExecutor = Callable[[ToolContext, dict[str, Any]], NormalizedResult]

_MAX_RETRIES = 2
_RETRY_BACKOFF_SEC = (0.5, 1.0)

_AUTH_HINTS = ("unauthorized", "invalid_auth", "token", "expired", "authentication", "401", "403")


def _classify_error(exc: Exception) -> ToolError:
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, RateLimitError):
        return ToolRateLimitedError(str(exc))
    msg = str(exc).lower()
    if any(h in msg for h in _AUTH_HINTS):
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _audit_resource_id(ctx: ToolContext) -> str:
    if ctx.task_id:
        return ctx.task_id
    if ctx.run_id:
        return ctx.run_id
    return ctx.org_id


def _audit_resource_type(ctx: ToolContext) -> str:
    if ctx.task_id or ctx.agent_id:
        return "agent_task"
    return RESOURCE_TYPE_WORKFLOW_RUN


def _audit_metadata(ctx: ToolContext, action: str, connector_id: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "action": action,
        "connector_id": connector_id,
        "step_id": ctx.step_id,
    }
    if ctx.agent_id:
        meta["agent_id"] = ctx.agent_id
    if ctx.task_id:
        meta["task_id"] = ctx.task_id
    if ctx.run_id:
        meta["run_id"] = ctx.run_id
    if extra:
        meta.update(extra)
    return meta


def _write_tool_audit(
    ctx: ToolContext,
    action: str,
    connector_id: str | None,
    audit_action: str,
    extra: dict[str, Any] | None = None,
) -> None:
    write_audit_event(
        ctx.client,
        ctx.org_id,
        ctx.actor_id,
        action=audit_action,
        resource_type=_audit_resource_type(ctx),
        resource_id=_audit_resource_id(ctx),
        metadata=_audit_metadata(ctx, action, connector_id, extra),
    )


def _enforce_tool_rate_limit(
    ctx: ToolContext,
    connector_type: str,
    connector_id: str,
) -> None:
    step_type = ctx.step_type or connector_type
    enforce_rate_limit(ctx.client, ctx.org_id, step_type, connector_type, connector_id)


def _hubspot_connector_and_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "hubspot", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active HubSpot connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "hubspot", cid)
    token, err = ensure_hubspot_access_token(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token:
        raise ToolAuthExpiredError(err or "HubSpot OAuth not connected")
    return cid, token


def _handle_hubspot_error(exc: HubSpotAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_hubspot_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    try:
        data = get_contact(
            token,
            contact_id=params.get("contact_id") or params.get("contactId"),
            email=params.get("email"),
            properties=params.get("properties"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.get",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_contacts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.contacts.update requires properties object")
    try:
        data = update_contact(token, str(contact_id), properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.update",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_notes_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    body = str(params.get("body") or params.get("note") or "")
    try:
        data = create_note(
            token,
            body=body,
            contact_id=params.get("contact_id") or params.get("contactId"),
            deal_id=params.get("deal_id") or params.get("dealId"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.notes.create",
        connector_id=cid,
        data={"note": data},
    )


def _exec_hubspot_notes_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    note_id = params.get("note_id") or params.get("noteId")
    if not note_id:
        raise ToolValidationError("hubspot.notes.delete requires note_id")
    try:
        delete_note(token, str(note_id))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.notes.delete",
        connector_id=cid,
        data={"note_id": str(note_id), "deleted": True},
    )


def _exec_hubspot_deals_update_stage(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    dealstage = params.get("dealstage") or params.get("stage")
    try:
        data = update_deal_stage(token, str(deal_id), str(dealstage))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.update_stage",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.contacts.create requires properties object")
    try:
        data = create_contact(token, properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.create",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_contacts_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("hubspot.contacts.delete requires contact_id")
    try:
        delete_contact(token, str(contact_id))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.delete",
        connector_id=cid,
        data={"contact_id": str(contact_id), "deleted": True},
    )


def _exec_hubspot_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    filter_groups = params.get("filter_groups") or params.get("filterGroups")
    if not isinstance(filter_groups, list) or not filter_groups:
        raise ToolValidationError("hubspot.contacts.search requires filter_groups array")
    try:
        data = search_contacts(
            token,
            filter_groups=filter_groups,
            properties=params.get("properties"),
            limit=int(params.get("limit") or 10),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.search",
        connector_id=cid,
        data={"search": data},
    )


def _exec_hubspot_deals_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    if not deal_id:
        raise ToolValidationError("hubspot.deals.get requires deal_id")
    try:
        data = get_deal(token, str(deal_id), properties=params.get("properties"))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.get",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_deals_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.deals.create requires properties object")
    try:
        data = create_deal(
            token,
            properties,
            contact_id=params.get("contact_id") or params.get("contactId"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.create",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_deals_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    if not deal_id:
        raise ToolValidationError("hubspot.deals.delete requires deal_id")
    try:
        delete_deal(token, str(deal_id))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.delete",
        connector_id=cid,
        data={"deal_id": str(deal_id), "deleted": True},
    )


def _exec_hubspot_deals_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    properties = params.get("properties")
    if not deal_id:
        raise ToolValidationError("hubspot.deals.update requires deal_id")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.deals.update requires properties object")
    try:
        data = update_deal(token, str(deal_id), properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.update",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_lists_add_contact(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    contact_id = params.get("contact_id") or params.get("contactId")
    if not list_id or not contact_id:
        raise ToolValidationError("hubspot.lists.add_contact requires list_id and contact_id")
    try:
        data = add_contact_to_list(token, str(list_id), str(contact_id))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.lists.add_contact",
        connector_id=cid,
        data={"membership": data},
    )


def _exec_hubspot_sequences_enroll(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    try:
        data = enroll_contact_in_sequence(
            token,
            contact_id=str(params.get("contact_id") or params.get("contactId")),
            sequence_id=str(params.get("sequence_id") or params.get("sequenceId")),
            sender_email=params.get("sender_email") or params.get("senderEmail"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.sequences.enroll",
        connector_id=cid,
        data={"enrollment": data},
    )


def _exec_hubspot_companies_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    filter_groups = params.get("filter_groups") or params.get("filterGroups")
    if not isinstance(filter_groups, list) or not filter_groups:
        raise ToolValidationError("hubspot.companies.search requires filter_groups array")
    try:
        data = search_companies(
            token,
            filter_groups=filter_groups,
            properties=params.get("properties"),
            limit=int(params.get("limit", 10)),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.companies.search",
        connector_id=cid,
        data=data,
    )


def _exec_hubspot_pipelines_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    try:
        data = list_deal_pipelines(token)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.pipelines.list",
        connector_id=cid,
        data=data,
    )


def _exec_hubspot_tickets_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.tickets.create requires properties object")
    try:
        data = create_ticket(token, properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.tickets.create",
        connector_id=cid,
        data={"ticket": data},
    )


def _salesforce_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "salesforce", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Salesforce connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "salesforce", cid)
    token, instance_url, err = ensure_salesforce_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not instance_url:
        raise ToolAuthExpiredError(err or "Salesforce OAuth not connected")
    return cid, token, instance_url


def _handle_salesforce_error(exc: SalesforceAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_salesforce_leads_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    lead_id = params.get("lead_id") or params.get("leadId")
    if not lead_id:
        raise ToolValidationError("salesforce.leads.get requires lead_id")
    fields = params.get("fields")
    field_list = fields if isinstance(fields, list) else None
    try:
        data = get_lead(instance_url, token, str(lead_id), fields=field_list)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.leads.get",
        connector_id=cid,
        data={"lead": data},
    )


def _exec_salesforce_leads_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    lead_id = params.get("lead_id") or params.get("leadId")
    fields = params.get("fields") or params.get("properties")
    if not lead_id:
        raise ToolValidationError("salesforce.leads.update requires lead_id")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.leads.update requires fields object")
    try:
        data = update_lead(instance_url, token, str(lead_id), fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.leads.update",
        connector_id=cid,
        data={"lead": data or {"id": lead_id, "updated": True}},
    )


def _exec_salesforce_accounts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    account_id = params.get("account_id") or params.get("accountId")
    if not account_id:
        raise ToolValidationError("salesforce.accounts.get requires account_id")
    fields = params.get("fields")
    field_list = fields if isinstance(fields, list) else None
    try:
        data = get_account(instance_url, token, str(account_id), fields=field_list)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.accounts.get",
        connector_id=cid,
        data={"account": data},
    )


def _exec_salesforce_opportunities_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    fields = params.get("fields") or params.get("properties")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.opportunities.create requires fields object")
    try:
        data = create_opportunity(instance_url, token, fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.opportunities.create",
        connector_id=cid,
        data={"opportunity": data},
    )


def _exec_salesforce_opportunities_update_stage(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    opportunity_id = params.get("opportunity_id") or params.get("opportunityId")
    stage_name = params.get("stage_name") or params.get("stageName") or params.get("stage")
    if not opportunity_id:
        raise ToolValidationError("salesforce.opportunities.update_stage requires opportunity_id")
    if not stage_name:
        raise ToolValidationError("salesforce.opportunities.update_stage requires stage_name")
    try:
        data = update_opportunity_stage(instance_url, token, str(opportunity_id), str(stage_name))
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.opportunities.update_stage",
        connector_id=cid,
        data={"opportunity": data or {"id": opportunity_id, "StageName": stage_name}},
    )


def _exec_salesforce_tasks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    fields = params.get("fields") or params.get("properties")
    if not isinstance(fields, dict):
        fields = {}
    subject = params.get("subject")
    if subject and "Subject" not in fields:
        fields = {**fields, "Subject": str(subject)}
    who_id = params.get("who_id") or params.get("whoId")
    what_id = params.get("what_id") or params.get("whatId")
    if who_id and "WhoId" not in fields:
        fields = {**fields, "WhoId": str(who_id)}
    if what_id and "WhatId" not in fields:
        fields = {**fields, "WhatId": str(what_id)}
    description = params.get("description") or params.get("body")
    if description and "Description" not in fields:
        fields = {**fields, "Description": str(description)}
    status = params.get("status")
    if status and "Status" not in fields:
        fields = {**fields, "Status": str(status)}
    if not fields.get("Subject"):
        raise ToolValidationError("salesforce.tasks.create requires subject or fields.Subject")
    try:
        data = create_task(instance_url, token, fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.tasks.create",
        connector_id=cid,
        data={"task": data},
    )


def _exec_salesforce_leads_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    fields = params.get("fields") or params.get("properties")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.leads.create requires fields object")
    try:
        data = create_lead(instance_url, token, fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.leads.create",
        connector_id=cid,
        data={"lead": data},
    )


def _exec_salesforce_leads_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    soql = params.get("soql")
    if soql and not isinstance(soql, str):
        raise ToolValidationError("salesforce.leads.search soql must be a string")
    if not soql and not any(params.get(k) for k in ("email", "company", "status")):
        raise ToolValidationError(
            "salesforce.leads.search requires soql or at least one of email, company, status"
        )
    try:
        data = search_leads(
            instance_url,
            token,
            soql=str(soql) if soql else None,
            email=params.get("email"),
            company=params.get("company"),
            status=params.get("status"),
            limit=int(params.get("limit") or 25),
        )
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.leads.search",
        connector_id=cid,
        data={"results": data},
    )


def _exec_salesforce_opportunities_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    opportunity_id = params.get("opportunity_id") or params.get("opportunityId")
    if not opportunity_id:
        raise ToolValidationError("salesforce.opportunities.get requires opportunity_id")
    fields = params.get("fields")
    field_list = fields if isinstance(fields, list) else None
    try:
        data = get_opportunity(instance_url, token, str(opportunity_id), fields=field_list)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.opportunities.get",
        connector_id=cid,
        data={"opportunity": data},
    )


def _exec_salesforce_opportunities_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    opportunity_id = params.get("opportunity_id") or params.get("opportunityId")
    fields = params.get("fields") or params.get("properties")
    if not opportunity_id:
        raise ToolValidationError("salesforce.opportunities.update requires opportunity_id")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.opportunities.update requires fields object")
    try:
        data = update_opportunity(instance_url, token, str(opportunity_id), fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.opportunities.update",
        connector_id=cid,
        data={"opportunity": data or {"id": opportunity_id, "updated": True}},
    )


def _exec_salesforce_accounts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    fields = params.get("fields") or params.get("properties")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.accounts.create requires fields object")
    try:
        data = create_account(instance_url, token, fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.accounts.create",
        connector_id=cid,
        data={"account": data},
    )


def _exec_salesforce_accounts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, instance_url = _salesforce_connector_and_session(ctx, params)
    account_id = params.get("account_id") or params.get("accountId")
    fields = params.get("fields") or params.get("properties")
    if not account_id:
        raise ToolValidationError("salesforce.accounts.update requires account_id")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("salesforce.accounts.update requires fields object")
    try:
        data = update_account(instance_url, token, str(account_id), fields)
    except SalesforceAPIError as exc:
        raise _handle_salesforce_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="salesforce.accounts.update",
        connector_id=cid,
        data={"account": data or {"id": account_id, "updated": True}},
    )


def _quickbooks_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "quickbooks", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active QuickBooks connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "quickbooks", cid)
    token, _realm, api_base, err = ensure_quickbooks_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not api_base:
        raise ToolAuthExpiredError(err or "QuickBooks OAuth not connected")
    return cid, token, api_base


def _handle_quickbooks_error(exc: QuickBooksAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_quickbooks_invoices_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_invoices(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.invoices.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_invoices_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    invoice_id = params.get("invoice_id") or params.get("invoiceId")
    if not invoice_id:
        raise ToolValidationError("quickbooks.invoices.get requires invoice_id")
    try:
        data = get_invoice(api_base, token, str(invoice_id))
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.invoices.get",
        connector_id=cid,
        data={"invoice": data.get("Invoice") or data},
    )


def _exec_quickbooks_payments_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_payments(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.payments.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_vendors_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    vendor_id = params.get("vendor_id") or params.get("vendorId")
    if not vendor_id:
        raise ToolValidationError("quickbooks.vendors.get requires vendor_id")
    try:
        data = get_vendor(api_base, token, str(vendor_id))
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.vendors.get",
        connector_id=cid,
        data={"vendor": data.get("Vendor") or data},
    )


def _exec_quickbooks_customers_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_customers(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.customers.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_customers_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    customer_id = params.get("customer_id") or params.get("customerId")
    if not customer_id:
        raise ToolValidationError("quickbooks.customers.get requires customer_id")
    try:
        data = get_customer(api_base, token, str(customer_id))
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.customers.get",
        connector_id=cid,
        data={"customer": data.get("Customer") or data},
    )


def _exec_quickbooks_customers_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    display_name = params.get("display_name") or params.get("displayName") or params.get("name")
    email = params.get("email")
    if not display_name and not email:
        raise ToolValidationError("quickbooks.customers.search requires display_name or email")
    try:
        data = search_customers(
            api_base,
            token,
            display_name=str(display_name) if display_name else None,
            email=str(email) if email else None,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.customers.search",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_vendors_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_vendors(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.vendors.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_accounts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_accounts(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.accounts.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_bills_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = list_bills(
            api_base,
            token,
            max_results=int(params.get("max_results") or params.get("limit") or 25),
            start_position=int(params.get("start_position") or params.get("startPosition") or 1),
        )
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.bills.list",
        connector_id=cid,
        data={"queryResponse": data.get("QueryResponse") or data},
    )


def _exec_quickbooks_bills_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    bill_id = params.get("bill_id") or params.get("billId")
    if not bill_id:
        raise ToolValidationError("quickbooks.bills.get requires bill_id")
    try:
        data = get_bill(api_base, token, str(bill_id))
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.bills.get",
        connector_id=cid,
        data={"bill": data.get("Bill") or data},
    )


def _exec_quickbooks_companyinfo_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    try:
        data = get_company_info(api_base, token)
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.companyinfo.get",
        connector_id=cid,
        data={"companyInfo": data.get("CompanyInfo") or data},
    )


def _payload_from_params(params: dict[str, Any], reserved: frozenset[str]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in reserved and v is not None}


_QB_WRITE_RESERVED = frozenset({"connector_id", "payload"})


def _exec_quickbooks_invoices_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    payload = _payload_from_params(params, _QB_WRITE_RESERVED)
    if not payload:
        raise ToolValidationError("quickbooks.invoices.create requires invoice payload")
    try:
        data = create_invoice(api_base, token, payload)
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.invoices.create",
        connector_id=cid,
        data={"invoice": data.get("Invoice") or data},
    )


def _exec_quickbooks_customers_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    payload = _payload_from_params(params, _QB_WRITE_RESERVED)
    if not payload:
        raise ToolValidationError("quickbooks.customers.create requires customer payload")
    try:
        data = create_customer(api_base, token, payload)
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.customers.create",
        connector_id=cid,
        data={"customer": data.get("Customer") or data},
    )


def _exec_quickbooks_payments_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    payload = _payload_from_params(params, _QB_WRITE_RESERVED)
    if not payload:
        raise ToolValidationError("quickbooks.payments.create requires payment payload")
    try:
        data = create_payment(api_base, token, payload)
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.payments.create",
        connector_id=cid,
        data={"payment": data.get("Payment") or data},
    )


def _exec_quickbooks_journalentries_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _quickbooks_connector_and_session(ctx, params)
    payload = _payload_from_params(params, _QB_WRITE_RESERVED)
    if not payload:
        raise ToolValidationError("quickbooks.journalentries.create requires journal entry payload")
    try:
        data = create_journal_entry(api_base, token, payload)
    except QuickBooksAPIError as exc:
        raise _handle_quickbooks_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="quickbooks.journalentries.create",
        connector_id=cid,
        data={"journalEntry": data.get("JournalEntry") or data},
    )


def _stripe_connector_and_key(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str | None]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "stripe", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Stripe connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "stripe", cid)
    try:
        api_key, stripe_account = resolve_stripe_credentials(ctx.client, ctx.org_id, cid, ctx.settings)
    except StripeAPIError as exc:
        raise _handle_stripe_error(exc) from exc
    return cid, api_key, stripe_account


def _handle_stripe_error(exc: StripeAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_stripe_invoices_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, stripe_account = _stripe_connector_and_key(ctx, params)
    try:
        data = list_invoices(
            api_key,
            stripe_account=stripe_account,
            customer_id=params.get("customer_id") or params.get("customerId"),
            status=params.get("status"),
            limit=int(params.get("limit") or params.get("max_results") or 10),
            starting_after=params.get("starting_after") or params.get("startingAfter"),
        )
    except StripeAPIError as exc:
        raise _handle_stripe_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="stripe.invoices.list",
        connector_id=cid,
        data={"invoices": data},
    )


def _exec_stripe_subscriptions_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key, stripe_account = _stripe_connector_and_key(ctx, params)
    subscription_id = params.get("subscription_id") or params.get("subscriptionId")
    if not subscription_id:
        raise ToolValidationError("stripe.subscriptions.get requires subscription_id")
    try:
        data = get_subscription(api_key, str(subscription_id), stripe_account=stripe_account)
    except StripeAPIError as exc:
        raise _handle_stripe_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="stripe.subscriptions.get",
        connector_id=cid,
        data={"subscription": data},
    )


def _pagerduty_str_list(params: dict[str, Any], *keys: str) -> list[str] | None:
    for key in keys:
        val = params.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            return [str(item) for item in val if item is not None]
        if isinstance(val, str):
            parts = [part.strip() for part in val.split(",") if part.strip()]
            return parts or None
    return None


def _pagerduty_connector_session(
    ctx: ToolContext, params: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn: dict[str, Any] | None = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "pagerduty", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active PagerDuty connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "pagerduty", cid)
    token, err = ensure_pagerduty_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token:
        raise ToolAuthExpiredError(err or "PagerDuty OAuth not connected")
    return cid, token, conn


def _pagerduty_connector_read(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    cid, token, _conn = _pagerduty_connector_session(ctx, params)
    return cid, token


def _pagerduty_connector_and_token(
    ctx: ToolContext, params: dict[str, Any]
) -> tuple[str, str, str]:
    cid, token, conn = _pagerduty_connector_session(ctx, params)
    config = conn.get("config") or {}
    from_email = (
        params.get("from_email")
        or params.get("fromEmail")
        or params.get("requester_email")
        or config.get("pagerduty_requester_email")
    )
    if not from_email:
        try:
            user = fetch_pagerduty_user(token)
            from_email = user.get("email")
        except PagerDutyAPIError:
            from_email = None
    if not from_email:
        raise ToolValidationError(
            "pagerduty actions require from_email or a connected user with email on the connector"
        )
    return cid, token, str(from_email)


def _handle_pagerduty_error(exc: PagerDutyAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_pagerduty_incidents_acknowledge(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, from_email = _pagerduty_connector_and_token(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.acknowledge requires incident_id")
    try:
        data = acknowledge_incident(token, str(incident_id), from_email=from_email)
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.acknowledge",
        connector_id=cid,
        data={"incidents": data.get("incidents", data)},
    )


def _exec_pagerduty_incidents_add_note(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, from_email = _pagerduty_connector_and_token(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    content = params.get("content") or params.get("note") or params.get("body")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.add_note requires incident_id")
    if not content:
        raise ToolValidationError("pagerduty.incidents.add_note requires content")
    try:
        data = add_incident_note(token, str(incident_id), str(content), from_email=from_email)
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.add_note",
        connector_id=cid,
        data={"note": data.get("note", data)},
    )


def _exec_pagerduty_incidents_escalate(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, from_email = _pagerduty_connector_and_token(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.escalate requires incident_id")
    level = params.get("escalation_level") or params.get("escalationLevel")
    level_int = int(level) if level is not None else None
    try:
        data = escalate_incident(
            token,
            str(incident_id),
            from_email=from_email,
            escalation_level=level_int,
        )
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.escalate",
        connector_id=cid,
        data={"incidents": data.get("incidents", data)},
    )


def _exec_pagerduty_incidents_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _pagerduty_connector_read(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.get requires incident_id")
    try:
        data = get_incident(token, str(incident_id))
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.get",
        connector_id=cid,
        data={"incident": data},
    )


def _exec_pagerduty_incidents_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _pagerduty_connector_read(ctx, params)
    try:
        data = list_incidents(
            token,
            statuses=_pagerduty_str_list(params, "statuses", "status"),
            service_ids=_pagerduty_str_list(params, "service_ids", "serviceIds", "service_id"),
            urgencies=_pagerduty_str_list(params, "urgencies", "urgency"),
            limit=int(params.get("limit") or params.get("max_results") or 25),
        )
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.list",
        connector_id=cid,
        data={"incidents": data.get("incidents", data), "more": data.get("more")},
    )


def _exec_pagerduty_incidents_notes_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _pagerduty_connector_read(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.notes.list requires incident_id")
    try:
        data = list_incident_notes(token, str(incident_id))
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.notes.list",
        connector_id=cid,
        data=data,
    )


def _exec_pagerduty_services_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _pagerduty_connector_read(ctx, params)
    try:
        data = list_services(
            token,
            query=params.get("query") or params.get("q"),
            limit=int(params.get("limit") or params.get("max_results") or 25),
        )
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.services.list",
        connector_id=cid,
        data={"services": data.get("services", data), "more": data.get("more")},
    )


def _exec_pagerduty_oncalls_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _pagerduty_connector_read(ctx, params)
    try:
        data = list_oncalls(
            token,
            schedule_ids=_pagerduty_str_list(params, "schedule_ids", "scheduleIds", "schedule_id"),
            escalation_policy_ids=_pagerduty_str_list(
                params, "escalation_policy_ids", "escalationPolicyIds", "escalation_policy_id"
            ),
            limit=int(params.get("limit") or params.get("max_results") or 25),
        )
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.oncalls.list",
        connector_id=cid,
        data={"oncalls": data.get("oncalls", data), "more": data.get("more")},
    )


def _exec_pagerduty_incidents_resolve(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, from_email = _pagerduty_connector_and_token(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.resolve requires incident_id")
    resolution = params.get("resolution") or params.get("resolve_note") or params.get("note")
    try:
        data = resolve_incident(
            token,
            str(incident_id),
            from_email=from_email,
            resolution=str(resolution) if resolution else None,
        )
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.resolve",
        connector_id=cid,
        data={"incidents": data.get("incidents", data)},
    )


def _exec_pagerduty_incidents_reassign(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, from_email = _pagerduty_connector_and_token(ctx, params)
    incident_id = params.get("incident_id") or params.get("incidentId")
    user_id = params.get("user_id") or params.get("userId") or params.get("assignee_id")
    if not incident_id:
        raise ToolValidationError("pagerduty.incidents.reassign requires incident_id")
    if not user_id:
        raise ToolValidationError("pagerduty.incidents.reassign requires user_id")
    try:
        data = reassign_incident(token, str(incident_id), str(user_id), from_email=from_email)
    except PagerDutyAPIError as exc:
        raise _handle_pagerduty_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="pagerduty.incidents.reassign",
        connector_id=cid,
        data={"incidents": data.get("incidents", data)},
    )


def _jira_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "jira", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Jira connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "jira", cid)
    token, cloud_id, err = ensure_jira_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not cloud_id:
        raise ToolAuthExpiredError(err or "Jira OAuth not connected")
    return cid, token, cloud_id


def _handle_jira_error(exc: JiraAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_jira_issues_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    project_key = params.get("project_key") or params.get("projectKey")
    summary = params.get("summary")
    issue_type = params.get("issue_type") or params.get("issueType") or "Task"
    if not project_key:
        raise ToolValidationError("jira.issues.create requires project_key")
    if not summary:
        raise ToolValidationError("jira.issues.create requires summary")
    extra = params.get("fields")
    field_dict = extra if isinstance(extra, dict) else None
    try:
        data = jira_create_issue(
            cloud_id,
            token,
            project_key=str(project_key),
            summary=str(summary),
            issue_type=str(issue_type),
            description=params.get("description"),
            fields=field_dict,
        )
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.create",
        connector_id=cid,
        data={"issue": data},
    )


def _exec_jira_issues_assign(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = params.get("issue_id") or params.get("issueId") or params.get("issue_key") or params.get("issueKey")
    account_id = params.get("account_id") or params.get("accountId") or params.get("assignee_account_id")
    if not issue_id:
        raise ToolValidationError("jira.issues.assign requires issue_id or issue_key")
    if not account_id:
        raise ToolValidationError("jira.issues.assign requires account_id")
    try:
        data = assign_issue(cloud_id, token, str(issue_id), str(account_id))
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.assign",
        connector_id=cid,
        data={"assigned": data or {"ok": True}},
    )


def _exec_jira_issues_transition(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = params.get("issue_id") or params.get("issueId") or params.get("issue_key") or params.get("issueKey")
    transition_id = params.get("transition_id") or params.get("transitionId")
    if not issue_id:
        raise ToolValidationError("jira.issues.transition requires issue_id or issue_key")
    if not transition_id:
        raise ToolValidationError("jira.issues.transition requires transition_id")
    try:
        data = transition_issue(cloud_id, token, str(issue_id), str(transition_id))
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.transition",
        connector_id=cid,
        data={"transition": data or {"ok": True}},
    )


def _exec_jira_issues_comment(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = params.get("issue_id") or params.get("issueId") or params.get("issue_key") or params.get("issueKey")
    body = params.get("body") or params.get("comment") or params.get("text")
    if not issue_id:
        raise ToolValidationError("jira.issues.comment requires issue_id or issue_key")
    if not body:
        raise ToolValidationError("jira.issues.comment requires body")
    try:
        data = add_issue_comment(cloud_id, token, str(issue_id), str(body))
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.comment",
        connector_id=cid,
        data={"comment": data},
    )


def _issue_id_from_params(params: dict[str, Any]) -> str | None:
    raw = params.get("issue_id") or params.get("issueId") or params.get("issue_key") or params.get("issueKey")
    return str(raw).strip() if raw else None


def _exec_jira_issues_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = _issue_id_from_params(params)
    if not issue_id:
        raise ToolValidationError("jira.issues.get requires issue_id or issue_key")
    fields = params.get("fields")
    field_list = fields if isinstance(fields, list) else None
    try:
        data = get_issue(cloud_id, token, issue_id, fields=field_list)
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.get",
        connector_id=cid,
        data={"issue": data},
    )


def _exec_jira_issues_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    jql = params.get("jql")
    if not jql:
        project = params.get("project_key") or params.get("projectKey")
        status = params.get("status")
        assignee = params.get("assignee")
        parts: list[str] = []
        if project:
            parts.append(f'project = "{project}"')
        if status:
            parts.append(f'status = "{status}"')
        if assignee:
            parts.append(f'assignee = "{assignee}"')
        jql = " AND ".join(parts) if parts else ""
    if not jql:
        raise ToolValidationError(
            "jira.issues.search requires jql or at least one of project_key, status, assignee"
        )
    fields = params.get("fields")
    field_list = fields if isinstance(fields, list) else None
    limit = int(params.get("limit") or params.get("max_results") or 50)
    try:
        data = search_issues(cloud_id, token, str(jql), max_results=limit, fields=field_list)
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.search",
        connector_id=cid,
        data={"search": data},
    )


def _exec_jira_issues_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = _issue_id_from_params(params)
    fields = params.get("fields") or {}
    if not issue_id:
        raise ToolValidationError("jira.issues.update requires issue_id or issue_key")
    if not isinstance(fields, dict) or not fields:
        summary = params.get("summary")
        description = params.get("description")
        if summary:
            fields = {"summary": summary}
        if description:
            fields = {**fields, "description": description}
    if not fields:
        raise ToolValidationError("jira.issues.update requires fields object or summary/description")
    try:
        data = update_issue(cloud_id, token, issue_id, fields)
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.update",
        connector_id=cid,
        data={"issue": data or {"ok": True}},
    )


def _exec_jira_issues_transitions_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    issue_id = _issue_id_from_params(params)
    if not issue_id:
        raise ToolValidationError("jira.issues.transitions.list requires issue_id or issue_key")
    try:
        data = list_issue_transitions(cloud_id, token, issue_id)
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.issues.transitions.list",
        connector_id=cid,
        data={"transitions": data},
    )


def _exec_jira_projects_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    try:
        data = list_projects(
            cloud_id,
            token,
            query=params.get("query"),
            max_results=int(params.get("limit") or params.get("max_results") or 50),
        )
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="jira.projects.list",
        connector_id=cid,
        data={"projects": data},
    )


def _exec_jira_users_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, cloud_id = _jira_connector_and_session(ctx, params)
    query = params.get("query") or params.get("email") or params.get("display_name")
    if not query:
        raise ToolValidationError("jira.users.search requires query, email, or display_name")
    try:
        data = search_users(
            cloud_id,
            token,
            str(query),
            max_results=int(params.get("limit") or params.get("max_results") or 20),
        )
    except JiraAPIError as exc:
        raise _handle_jira_error(exc) from exc
    users = data if isinstance(data, list) else data.get("users") or data
    return NormalizedResult(
        success=True,
        action="jira.users.search",
        connector_id=cid,
        data={"users": users},
    )


def _slack_connector_and_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.connector_tool_auth import resolve_slack_bot_token

    conn = _connector_by_type(ctx, "slack", params)
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "slack", cid)
    token = resolve_slack_bot_token(ctx.client, ctx.org_id, cid, ctx.settings)
    if not token:
        raise ToolAuthExpiredError("Slack connector missing bot token")
    return cid, token


def _exec_slack_post_message(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    channel = (params.get("channel") or "").strip()
    text = (params.get("message") or params.get("text") or "").strip()
    if not channel:
        raise ToolValidationError("Slack channel is required")
    if not text:
        raise ToolValidationError("Slack message is required")
    result = send_slack_message(token, channel, text)
    return NormalizedResult(
        success=True,
        action="slack.post_message",
        connector_id=cid,
        latency_ms=int(result.get("_latency_ms", 0) or 0),
        data={"executed": True, "channel": channel, "ts": result.get("ts"), "ok": True},
    )


def _exec_slack_conversations_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    try:
        data = list_conversations(
            token,
            types=str(params.get("types") or "public_channel,private_channel"),
            limit=int(params.get("limit") or 100),
            cursor=params.get("cursor"),
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(
        success=True,
        action="slack.conversations.list",
        connector_id=cid,
        latency_ms=int(data.get("_latency_ms", 0) or 0),
        data={"channels": data.get("channels") or [], "response_metadata": data.get("response_metadata")},
    )


def _exec_slack_conversations_history(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    channel = params.get("channel")
    if not channel:
        raise ToolValidationError("slack.conversations.history requires channel")
    try:
        data = conversation_history(
            token,
            str(channel),
            limit=int(params.get("limit") or 50),
            cursor=params.get("cursor"),
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(
        success=True,
        action="slack.conversations.history",
        connector_id=cid,
        latency_ms=int(data.get("_latency_ms", 0) or 0),
        data={"messages": data.get("messages") or [], "response_metadata": data.get("response_metadata")},
    )


def _exec_slack_users_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    try:
        data = list_users(
            token,
            limit=int(params.get("limit") or 100),
            cursor=params.get("cursor"),
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(
        success=True,
        action="slack.users.list",
        connector_id=cid,
        latency_ms=int(data.get("_latency_ms", 0) or 0),
        data={"members": data.get("members") or [], "response_metadata": data.get("response_metadata")},
    )


def _exec_email_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    if not connector_id:
        raise ToolValidationError("email.send requires connector_id")
    conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("Connector not found")
    if conn.get("type") != "email":
        raise ToolValidationError("Connector must be type email")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "email", cid)
    to_addr = (params.get("to") or "").strip()
    subject = str(params.get("subject") or "")
    body = str(params.get("body") or "")
    if not to_addr:
        raise ToolValidationError("email.send requires to")
    content_type = (params.get("content_type") or "text/plain").strip()
    if content_type not in ("text/plain", "text/html"):
        content_type = "text/plain"
    conn_config = conn.get("config") or {}
    use_tls = conn_config.get("use_tls", True)
    smtp_host = get_decrypted_secret(ctx.client, cid, "SMTP_HOST", ctx.settings)
    smtp_port = get_decrypted_secret(ctx.client, cid, "SMTP_PORT", ctx.settings)
    smtp_user = get_decrypted_secret(ctx.client, cid, "SMTP_USERNAME", ctx.settings)
    smtp_pass = get_decrypted_secret(ctx.client, cid, "SMTP_PASSWORD", ctx.settings)
    smtp_from = get_decrypted_secret(ctx.client, cid, "SMTP_FROM", ctx.settings)
    if not smtp_host:
        raise ToolValidationError("Email connector missing SMTP_HOST secret")
    if not smtp_from:
        raise ToolValidationError("Email connector missing SMTP_FROM secret")
    port = int(smtp_port) if smtp_port else (587 if use_tls else 25)
    to_domain = extract_to_domain(to_addr)
    subj_h = _subject_hash(subject)
    body_h = _body_hash(body)
    msg_id, latency_ms = send_email_smtp(
        host=smtp_host,
        port=port,
        username=smtp_user or "",
        password=smtp_pass or "",
        from_addr=smtp_from,
        to_addr=to_addr,
        subject=subject,
        body=body,
        content_type=content_type,
        use_tls=use_tls,
    )
    out: dict[str, Any] = {
        "simulated": False,
        "to_domain": to_domain,
        "subject_hash": subj_h,
        "body_hash": body_h,
        "content_type": content_type,
    }
    if msg_id:
        out["message_id"] = msg_id[:200]
    return NormalizedResult(
        success=True,
        action="email.send",
        connector_id=cid,
        latency_ms=latency_ms,
        data=out,
    )


def _email_connector(ctx: ToolContext, params: dict[str, Any]) -> str:
    connector_id = params.get("connector_id") or ctx.connector_id
    if not connector_id:
        raise ToolValidationError("email action requires connector_id")
    conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn or conn.get("type") != "email":
        raise ToolValidationError("Active email connector required")
    return str(conn["id"])


def _exec_email_messages_queue(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid = _email_connector(ctx, params)
    return NormalizedResult(success=True, action="email.messages.queue", connector_id=cid, data={"queue": [], "note": "SMTP connectors do not expose a remote queue API"})


def _exec_email_delivery_status(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid = _email_connector(ctx, params)
    message_id = params.get("message_id")
    return NormalizedResult(
        success=True,
        action="email.delivery.status",
        connector_id=cid,
        data={"message_id": message_id, "status": "unknown", "note": "Delivery status requires provider webhooks"},
    )


def _exec_email_send_template(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    template = params.get("template") or params.get("template_id")
    variables = params.get("variables") or {}
    body = str(params.get("body") or "")
    if template and isinstance(variables, dict):
        for key, value in variables.items():
            body = body.replace(f"{{{{{key}}}}}", str(value))
    merged = {**params, "body": body or str(template or "")}
    result = _exec_email_send(ctx, merged)
    return NormalizedResult(success=True, action="email.send.template", connector_id=result.connector_id, data=result.data)


def _exec_email_batch_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    messages = params.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ToolValidationError("email.batch.send requires messages[]")
    cid = _email_connector(ctx, params)
    sent = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        merged = {**params, **item}
        sent.append(_exec_email_send(ctx, merged).data)
    return NormalizedResult(success=True, action="email.batch.send", connector_id=cid, data={"sent": sent, "count": len(sent)})


def _exec_webhook_post(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    if not connector_id:
        raise ToolValidationError("webhook.post requires connector_id")
    conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("Connector not found")
    if conn.get("type") != "webhook":
        raise ToolValidationError("Connector must be type webhook")
    if conn.get("status") != "active":
        raise ToolValidationError("Connector must be active")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "webhook", cid)
    conn_cfg = parse_connector_config(conn.get("config") or {})
    allowed_hosts = conn_cfg["allowed_hosts"]
    target_host = allowed_hosts[0]
    path = params.get("path") or conn_cfg.get("default_path") or "/"
    path = validate_path(str(path))
    payload = params.get("payload")
    if payload is None:
        raise ToolValidationError("webhook.post requires payload")
    payload_bytes = coerce_payload(payload)
    if len(payload_bytes) > conn_cfg["max_payload_bytes"]:
        raise ToolValidationError("webhook.post payload exceeds max_payload_bytes")
    step_headers = params.get("headers") or {}
    sanitize_headers(step_headers)
    ips = resolve_and_validate_host(target_host)
    connect_ip = ips[0]
    bearer_token = get_decrypted_secret(ctx.client, cid, "WEBHOOK_BEARER_TOKEN", ctx.settings)
    hmac_secret = get_decrypted_secret(ctx.client, cid, "WEBHOOK_HMAC_SECRET", ctx.settings)
    secret_headers: dict[str, str] = {}
    rows = (
        ctx.client.table("connector_secrets")
        .select("key_name, encrypted_value")
        .eq("connector_id", cid)
        .execute()
    )
    for row in rows.data or []:
        key_name = row.get("key_name", "")
        if not key_name.startswith("WEBHOOK_HEADER_"):
            continue
        header_name = key_name[len("WEBHOOK_HEADER_") :].replace("_", "-")
        if header_name.lower() not in WEBHOOK_ALLOWED_HEADERS:
            raise ToolValidationError(f"Header {header_name!r} not allowlisted")
        secret_val = decrypt_secret(row["encrypted_value"], ctx.settings.connector_secrets_encryption_key)
        secret_headers[header_name] = secret_val
    headers, preview_keys, request_id = build_headers(
        step_headers=step_headers,
        secret_headers=secret_headers,
        bearer_token=bearer_token,
        hmac_secret=hmac_secret,
        payload_bytes=payload_bytes,
    )
    build_url(target_host, path, conn_cfg["allowed_schemes"])
    p_hash = _payload_hash(payload_bytes)
    status_code, response_time_ms = send_webhook(
        host=target_host,
        path=path,
        connect_ip=connect_ip,
        payload_bytes=payload_bytes,
        headers=headers,
        timeout_seconds=conn_cfg["timeout_seconds"],
        retry_count=conn_cfg["retry_count"],
        retry_backoff_ms=conn_cfg["retry_backoff_ms"],
    )
    return NormalizedResult(
        success=True,
        action="webhook.post",
        connector_id=cid,
        latency_ms=int(response_time_ms),
        data={
            "simulated": False,
            "target_host": target_host,
            "path": path,
            "payload_hash": p_hash,
            "payload_bytes": len(payload_bytes),
            "status_code": status_code,
            "response_time_ms": int(response_time_ms),
            "retry_count_used": conn_cfg["retry_count"],
            "request_id": request_id,
            "headers_preview": preview_keys,
        },
    )


def _connector_by_type(ctx: ToolContext, connector_type: str, params: dict[str, Any]) -> dict:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, connector_type, environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError(f"No active {connector_type} connector found for org")
    return conn


def _zendesk_credentials(
    ctx: ToolContext, params: dict[str, Any]
) -> tuple[str, str, str | None, str | None, str | None]:
    from app.connectors.connector_tool_auth import resolve_zendesk_auth

    conn = _connector_by_type(ctx, "zendesk", params)
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "zendesk", cid)
    try:
        subdomain, email, api_token, oauth_token = resolve_zendesk_auth(
            ctx.client,
            ctx.org_id,
            conn,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    if oauth_token:
        return cid, subdomain, None, None, oauth_token
    if not email or not api_token:
        raise ToolAuthExpiredError("Zendesk OAuth or email/api_token secrets not configured")
    return cid, subdomain, email, api_token, None


def _github_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.connector_tool_auth import resolve_github_access_token

    conn = _connector_by_type(ctx, "github", params)
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "github", cid)
    token = resolve_github_access_token(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=ctx.environment_name,
    )
    if not token:
        raise ToolAuthExpiredError("GitHub OAuth or PAT not configured")
    return cid, token


def _github_owner_repo(ctx: ToolContext, cid: str, params: dict[str, Any]) -> tuple[str, str]:
    conn = get_connector(ctx.client, ctx.org_id, cid, environment_name=ctx.environment_name) or {}
    cfg = conn.get("config") or {}
    owner = params.get("owner") or cfg.get("owner")
    repo = params.get("repo") or cfg.get("repo")
    if not owner or not repo:
        raise ToolValidationError("GitHub action requires owner and repo")
    return str(owner), str(repo)


def _google_vendor_token(ctx: ToolContext, vendor: str, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.google_vendor_oauth import ensure_google_vendor_session

    conn = _connector_by_type(ctx, vendor, params)
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, vendor, cid)
    oauth_token, oauth_err = ensure_google_vendor_session(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if oauth_token:
        return cid, oauth_token
    if vendor == "google_calendar":
        legacy = get_decrypted_secret(ctx.client, cid, "access_token", ctx.settings)
        if legacy:
            return cid, legacy
    raise ToolAuthExpiredError(oauth_err or f"{vendor} not connected")


def _google_calendar_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    return _google_vendor_token(ctx, "google_calendar", params)


def _ga_property_id(conn: dict[str, Any], params: dict[str, Any]) -> str:
    pid = params.get("property_id") or params.get("propertyId")
    if pid:
        return str(pid).strip()
    cfg = conn.get("config") or {}
    linked = (cfg.get("property_id") or cfg.get("propertyId") or "").strip()
    if not linked:
        raise ToolValidationError("analytics actions require property_id or linked GA4 property")
    return linked


def _vendor_api_error(exc: Exception, vendor: str) -> ToolError:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return ToolRateLimitedError(str(exc))
    if status in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_zendesk_tickets_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id") or params.get("ticketId")
    if not ticket_id:
        raise ToolValidationError("zendesk.tickets.get requires ticket_id")
    try:
        ticket = get_ticket(
            subdomain,
            email,
            token,
            ticket_id,
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.get", connector_id=cid, data={"ticket": ticket})


def _exec_zendesk_tickets_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    subject = params.get("subject")
    comment = params.get("comment") or params.get("body")
    if not subject or not comment:
        raise ToolValidationError("zendesk.tickets.create requires subject and comment")
    try:
        ticket = create_ticket(
            subdomain,
            email,
            token,
            subject=str(subject),
            comment=str(comment),
            requester_email=params.get("requester_email") or params.get("requesterEmail"),
            priority=params.get("priority"),
            tags=params.get("tags"),
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.create", connector_id=cid, data={"ticket": ticket})


def _exec_zendesk_tickets_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id") or params.get("ticketId")
    if not ticket_id:
        raise ToolValidationError("zendesk.tickets.update requires ticket_id")
    try:
        ticket = update_ticket(
            subdomain,
            email,
            token,
            ticket_id,
            status=params.get("status"),
            priority=params.get("priority"),
            comment=params.get("comment"),
            tags=params.get("tags"),
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.update", connector_id=cid, data={"ticket": ticket})


def _exec_zendesk_tickets_close(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id") or params.get("ticketId")
    if not ticket_id:
        raise ToolValidationError("zendesk.tickets.close requires ticket_id")
    try:
        ticket = close_ticket(
            subdomain,
            email,
            token,
            ticket_id,
            comment=params.get("comment"),
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.close", connector_id=cid, data={"ticket": ticket})


def _exec_zendesk_tickets_add_tags(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id") or params.get("ticketId")
    tags = params.get("tags")
    if not ticket_id or not isinstance(tags, list) or not tags:
        raise ToolValidationError("zendesk.tickets.add_tags requires ticket_id and tags[]")
    try:
        result = add_ticket_tags(
            subdomain,
            email,
            token,
            ticket_id,
            [str(t) for t in tags],
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.add_tags", connector_id=cid, data={"tags": result})


def _exec_zendesk_tickets_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    try:
        tickets = list_tickets(
            subdomain,
            email,
            token,
            status=params.get("status"),
            limit=int(params.get("limit") or 25),
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(
        success=True,
        action="zendesk.tickets.list",
        connector_id=cid,
        data={"tickets": tickets},
    )


def _exec_zendesk_users_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
    user_id = params.get("user_id") or params.get("userId")
    if not user_id:
        raise ToolValidationError("zendesk.users.get requires user_id")
    try:
        user = zendesk_get_user(
            subdomain,
            email,
            token,
            user_id,
            oauth_access_token=oauth_token,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(
        success=True,
        action="zendesk.users.get",
        connector_id=cid,
        data={"user": user},
    )


def _microsoft365_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.connector_tool_auth import resolve_microsoft365_access_token

    conn = _connector_by_type(ctx, "microsoft365", params)
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "microsoft365", cid)
    token = resolve_microsoft365_access_token(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=ctx.environment_name,
    )
    if not token:
        raise ToolAuthExpiredError("Microsoft 365 OAuth not connected")
    return cid, token


def _exec_microsoft365_users_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.microsoft365 import Microsoft365APIError, get_user

    cid, token = _microsoft365_token(ctx, params)
    user_id = str(params.get("user_id") or params.get("userId") or "me")
    try:
        user = get_user(token, user_id=user_id)
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(
        success=True,
        action="microsoft365.users.get",
        connector_id=cid,
        data={"user": user},
    )


def _exec_microsoft365_mail_messages_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.microsoft365 import Microsoft365APIError, list_mail_messages

    cid, token = _microsoft365_token(ctx, params)
    user_id = str(params.get("user_id") or params.get("userId") or "me")
    try:
        data = list_mail_messages(
            token,
            user_id=user_id,
            top=int(params.get("top") or params.get("limit") or 25),
            filter_query=params.get("filter") or params.get("filter_query"),
        )
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(
        success=True,
        action="microsoft365.mail.messages.list",
        connector_id=cid,
        data=data,
    )


def _exec_microsoft365_calendar_events_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.microsoft365 import Microsoft365APIError, list_calendar_events

    cid, token = _microsoft365_token(ctx, params)
    user_id = str(params.get("user_id") or params.get("userId") or "me")
    try:
        data = list_calendar_events(
            token,
            user_id=user_id,
            top=int(params.get("top") or params.get("limit") or 25),
            start_datetime=params.get("start") or params.get("start_datetime"),
            end_datetime=params.get("end") or params.get("end_datetime"),
        )
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(
        success=True,
        action="microsoft365.calendar.events.list",
        connector_id=cid,
        data=data,
    )


def _exec_github_pulls_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    try:
        pulls = list_pull_requests(token, owner, repo, state=str(params.get("state") or "open"))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.pulls.list", connector_id=cid, data={"pull_requests": pulls})


def _exec_github_issues_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    issue_number = params.get("issue_number") or params.get("issueNumber")
    if not issue_number:
        raise ToolValidationError("github.issues.get requires issue_number")
    try:
        issue = get_issue(token, owner, repo, int(issue_number))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.issues.get", connector_id=cid, data={"issue": issue})


def _exec_github_repos_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    try:
        repository = get_repository(token, owner, repo)
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.repos.get", connector_id=cid, data={"repository": repository})


def _exec_github_issues_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    title = params.get("title")
    if not title:
        raise ToolValidationError("github.issues.create requires title")
    try:
        issue = create_issue(token, owner, repo, title=str(title), body=params.get("body"), labels=params.get("labels"))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.issues.create", connector_id=cid, data={"issue": issue})


def _exec_github_issues_comment(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    issue_number = params.get("issue_number") or params.get("issueNumber")
    body = params.get("body") or params.get("comment")
    if not issue_number or not body:
        raise ToolValidationError("github.issues.comment requires issue_number and body")
    try:
        comment = create_issue_comment(token, owner, repo, int(issue_number), str(body))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.issues.comment", connector_id=cid, data={"comment": comment})


def _exec_github_pulls_request_reviewer(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    pull_number = params.get("pull_number") or params.get("pullNumber")
    reviewers = params.get("reviewers")
    if not pull_number or not isinstance(reviewers, list):
        raise ToolValidationError("github.pulls.request_reviewer requires pull_number and reviewers[]")
    try:
        result = request_pull_request_reviewer(
            token, owner, repo, int(pull_number), [str(r) for r in reviewers]
        )
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(
        success=True,
        action="github.pulls.request_reviewer",
        connector_id=cid,
        data={"requested_reviewers": result},
    )


def _exec_github_actions_dispatch(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    workflow_id = params.get("workflow_id") or params.get("workflowId")
    ref = params.get("ref")
    if not workflow_id or not ref:
        raise ToolValidationError("github.actions.dispatch requires workflow_id and ref")
    inputs = params.get("inputs")
    if inputs is not None and not isinstance(inputs, dict):
        raise ToolValidationError("github.actions.dispatch inputs must be an object")
    try:
        dispatch_workflow(
            token,
            owner,
            repo,
            str(workflow_id),
            ref=str(ref),
            inputs={str(k): str(v) for k, v in inputs.items()} if inputs else None,
        )
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(
        success=True,
        action="github.actions.dispatch",
        connector_id=cid,
        data={"dispatched": True, "workflow_id": str(workflow_id), "ref": str(ref)},
    )


def _exec_github_pulls_merge(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    pull_number = params.get("pull_number") or params.get("pullNumber")
    if not pull_number:
        raise ToolValidationError("github.pulls.merge requires pull_number")
    try:
        result = merge_pull_request(
            token,
            owner,
            repo,
            int(pull_number),
            commit_title=params.get("commit_title") or params.get("commitTitle"),
            commit_message=params.get("commit_message") or params.get("commitMessage"),
            merge_method=params.get("merge_method") or params.get("mergeMethod"),
        )
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.pulls.merge", connector_id=cid, data=result)


def _exec_github_releases_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    tag_name = params.get("tag_name") or params.get("tagName")
    if not tag_name:
        raise ToolValidationError("github.releases.create requires tag_name")
    try:
        release = create_release(
            token,
            owner,
            repo,
            tag_name=str(tag_name),
            name=params.get("name"),
            body=params.get("body"),
            draft=bool(params.get("draft", False)),
            prerelease=bool(params.get("prerelease", False)),
            target_commitish=params.get("target_commitish") or params.get("targetCommitish"),
        )
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.releases.create", connector_id=cid, data={"release": release})


def _exec_github_issues_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    try:
        issues = list_issues(token, owner, repo, state=str(params.get("state") or "open"))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.issues.list", connector_id=cid, data={"issues": issues})


def _exec_github_pulls_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    pull_number = params.get("pull_number") or params.get("pullNumber")
    if not pull_number:
        raise ToolValidationError("github.pulls.get requires pull_number")
    try:
        pull = get_pull_request(token, owner, repo, int(pull_number))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.pulls.get", connector_id=cid, data={"pull_request": pull})


def _exec_github_pulls_close(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _github_token(ctx, params)
    owner, repo = _github_owner_repo(ctx, cid, params)
    pull_number = params.get("pull_number") or params.get("pullNumber")
    if not pull_number:
        raise ToolValidationError("github.pulls.close requires pull_number")
    try:
        pull = close_pull_request(token, owner, repo, int(pull_number))
    except GitHubAPIError as exc:
        raise _vendor_api_error(exc, "github") from exc
    return NormalizedResult(success=True, action="github.pulls.close", connector_id=cid, data={"pull_request": pull})


def _exec_calendar_freebusy(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_calendar_token(ctx, params)
    calendar_id = str(params.get("calendar_id") or params.get("calendarId") or "primary")
    time_min = params.get("time_min") or params.get("timeMin")
    time_max = params.get("time_max") or params.get("timeMax")
    if not time_min or not time_max:
        time_min, time_max = default_window_iso()
    try:
        data = query_freebusy(token, calendar_id=calendar_id, time_min=str(time_min), time_max=str(time_max))
    except GoogleCalendarAPIError as exc:
        raise _vendor_api_error(exc, "google_calendar") from exc
    return NormalizedResult(success=True, action="calendar.freebusy", connector_id=cid, data={"freebusy": data})


def _exec_calendar_events_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_calendar_token(ctx, params)
    summary = params.get("summary") or params.get("title")
    start_iso = params.get("start") or params.get("start_iso")
    end_iso = params.get("end") or params.get("end_iso")
    if not summary or not start_iso or not end_iso:
        raise ToolValidationError("calendar.events.create requires summary, start, end")
    try:
        event = create_event(
            token,
            calendar_id=str(params.get("calendar_id") or "primary"),
            summary=str(summary),
            description=params.get("description"),
            start_iso=str(start_iso),
            end_iso=str(end_iso),
            attendees=params.get("attendees"),
        )
    except GoogleCalendarAPIError as exc:
        raise _vendor_api_error(exc, "google_calendar") from exc
    return NormalizedResult(success=True, action="calendar.events.create", connector_id=cid, data={"event": event})


def _exec_calendar_events_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_calendar_token(ctx, params)
    calendar_id = str(params.get("calendar_id") or params.get("calendarId") or "primary")
    time_min = params.get("time_min") or params.get("timeMin")
    time_max = params.get("time_max") or params.get("timeMax")
    if not time_min or not time_max:
        time_min, time_max = default_window_iso(hours=int(params.get("hours") or 168))
    try:
        data = list_events(
            token,
            calendar_id=calendar_id,
            time_min=str(time_min),
            time_max=str(time_max),
            max_results=int(params.get("max_results") or params.get("maxResults") or 25),
        )
    except GoogleCalendarAPIError as exc:
        raise _vendor_api_error(exc, "google_calendar") from exc
    return NormalizedResult(
        success=True,
        action="calendar.events.list",
        connector_id=cid,
        data={"events": data.get("items") or [], "nextPageToken": data.get("nextPageToken")},
    )


def _exec_calendar_calendars_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _google_calendar_token(ctx, params)
    try:
        data = list_calendars(token, max_results=int(params.get("max_results") or params.get("maxResults") or 25))
    except GoogleCalendarAPIError as exc:
        raise _vendor_api_error(exc, "google_calendar") from exc
    return NormalizedResult(
        success=True,
        action="calendar.calendars.list",
        connector_id=cid,
        data={"calendars": data.get("items") or [], "nextPageToken": data.get("nextPageToken")},
    )


def _exec_analytics_properties_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_analytics import GoogleAnalyticsAPIError, list_ga4_properties

    cid, token = _google_vendor_token(ctx, "google_analytics", params)
    try:
        properties = list_ga4_properties(token)
    except GoogleAnalyticsAPIError as exc:
        raise _vendor_api_error(exc, "google_analytics") from exc
    return NormalizedResult(
        success=True,
        action="analytics.properties.list",
        connector_id=cid,
        data={"properties": properties},
    )


def _exec_analytics_reports_run(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_analytics import GoogleAnalyticsAPIError, run_ga4_report

    conn = _connector_by_type(ctx, "google_analytics", params)
    cid, token = _google_vendor_token(ctx, "google_analytics", params)
    property_id = _ga_property_id(conn, params)
    try:
        report = run_ga4_report(
            token,
            property_id,
            start_date=str(params.get("start_date") or params.get("startDate") or "7daysAgo"),
            end_date=str(params.get("end_date") or params.get("endDate") or "today"),
            dimensions=params.get("dimensions"),
            metrics=params.get("metrics"),
        )
    except GoogleAnalyticsAPIError as exc:
        raise _vendor_api_error(exc, "google_analytics") from exc
    return NormalizedResult(
        success=True,
        action="analytics.reports.run",
        connector_id=cid,
        data={"property_id": property_id, "report": report},
    )


def _exec_analytics_metadata_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_analytics import GoogleAnalyticsAPIError, list_property_metadata

    conn = _connector_by_type(ctx, "google_analytics", params)
    cid, token = _google_vendor_token(ctx, "google_analytics", params)
    property_id = _ga_property_id(conn, params)
    try:
        metadata = list_property_metadata(token, property_id)
    except GoogleAnalyticsAPIError as exc:
        raise _vendor_api_error(exc, "google_analytics") from exc
    return NormalizedResult(
        success=True,
        action="analytics.metadata.list",
        connector_id=cid,
        data={"property_id": property_id, "metadata": metadata},
    )


def _exec_gmail_messages_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.gmail import GmailAPIError, list_messages

    cid, token = _google_vendor_token(ctx, "gmail", params)
    try:
        data = list_messages(
            token,
            query=params.get("query") or params.get("q"),
            max_results=int(params.get("max_results") or params.get("maxResults") or 25),
        )
    except GmailAPIError as exc:
        raise _vendor_api_error(exc, "gmail") from exc
    return NormalizedResult(success=True, action="gmail.messages.list", connector_id=cid, data=data)


def _exec_gmail_messages_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.gmail import GmailAPIError, get_message

    cid, token = _google_vendor_token(ctx, "gmail", params)
    message_id = params.get("message_id") or params.get("messageId")
    if not message_id:
        raise ToolValidationError("gmail.messages.get requires message_id")
    try:
        data = get_message(token, str(message_id))
    except GmailAPIError as exc:
        raise _vendor_api_error(exc, "gmail") from exc
    return NormalizedResult(success=True, action="gmail.messages.get", connector_id=cid, data={"message": data})


def _exec_gmail_messages_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.gmail import GmailAPIError, send_message

    cid, token = _google_vendor_token(ctx, "gmail", params)
    to = params.get("to")
    subject = params.get("subject")
    body = params.get("body") or params.get("text")
    if not to or not subject or not body:
        raise ToolValidationError("gmail.messages.send requires to, subject, body")
    try:
        data = send_message(token, to=str(to), subject=str(subject), body=str(body))
    except GmailAPIError as exc:
        raise _vendor_api_error(exc, "gmail") from exc
    return NormalizedResult(success=True, action="gmail.messages.send", connector_id=cid, data=data)


def _exec_gmail_labels_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.gmail import GmailAPIError, list_labels

    cid, token = _google_vendor_token(ctx, "gmail", params)
    try:
        data = list_labels(token, user_id=str(params.get("user_id") or params.get("userId") or "me"))
    except GmailAPIError as exc:
        raise _vendor_api_error(exc, "gmail") from exc
    return NormalizedResult(success=True, action="gmail.labels.list", connector_id=cid, data=data)


def _exec_drive_files_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_drive import GoogleDriveAPIError, list_files

    cid, token = _google_vendor_token(ctx, "google_drive", params)
    try:
        data = list_files(
            token,
            page_size=int(params.get("page_size") or params.get("pageSize") or 25),
            query=params.get("query") or params.get("q"),
        )
    except GoogleDriveAPIError as exc:
        raise _vendor_api_error(exc, "google_drive") from exc
    return NormalizedResult(success=True, action="drive.files.list", connector_id=cid, data=data)


def _exec_drive_files_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_drive import GoogleDriveAPIError, get_file

    cid, token = _google_vendor_token(ctx, "google_drive", params)
    file_id = params.get("file_id") or params.get("fileId")
    if not file_id:
        raise ToolValidationError("drive.files.get requires file_id")
    try:
        data = get_file(token, str(file_id))
    except GoogleDriveAPIError as exc:
        raise _vendor_api_error(exc, "google_drive") from exc
    return NormalizedResult(success=True, action="drive.files.get", connector_id=cid, data={"file": data})


def _exec_drive_permissions_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_drive import GoogleDriveAPIError, list_permissions

    cid, token = _google_vendor_token(ctx, "google_drive", params)
    file_id = params.get("file_id") or params.get("fileId")
    if not file_id:
        raise ToolValidationError("drive.permissions.list requires file_id")
    try:
        data = list_permissions(token, str(file_id))
    except GoogleDriveAPIError as exc:
        raise _vendor_api_error(exc, "google_drive") from exc
    return NormalizedResult(success=True, action="drive.permissions.list", connector_id=cid, data=data)


def _exec_sheets_spreadsheets_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_sheets import GoogleSheetsAPIError, get_spreadsheet

    cid, token = _google_vendor_token(ctx, "google_sheets", params)
    spreadsheet_id = params.get("spreadsheet_id") or params.get("spreadsheetId")
    if not spreadsheet_id:
        raise ToolValidationError("sheets.spreadsheets.get requires spreadsheet_id")
    try:
        data = get_spreadsheet(token, str(spreadsheet_id))
    except GoogleSheetsAPIError as exc:
        raise _vendor_api_error(exc, "google_sheets") from exc
    return NormalizedResult(
        success=True,
        action="sheets.spreadsheets.get",
        connector_id=cid,
        data={"spreadsheet": data},
    )


def _exec_sheets_values_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_sheets import GoogleSheetsAPIError, get_values

    cid, token = _google_vendor_token(ctx, "google_sheets", params)
    spreadsheet_id = params.get("spreadsheet_id") or params.get("spreadsheetId")
    range_a1 = params.get("range") or params.get("rangeA1")
    if not spreadsheet_id or not range_a1:
        raise ToolValidationError("sheets.values.get requires spreadsheet_id and range")
    try:
        data = get_values(token, str(spreadsheet_id), str(range_a1))
    except GoogleSheetsAPIError as exc:
        raise _vendor_api_error(exc, "google_sheets") from exc
    return NormalizedResult(success=True, action="sheets.values.get", connector_id=cid, data=data)


def _exec_sheets_values_batch_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_sheets import GoogleSheetsAPIError, batch_get_values

    cid, token = _google_vendor_token(ctx, "google_sheets", params)
    spreadsheet_id = params.get("spreadsheet_id") or params.get("spreadsheetId")
    ranges = params.get("ranges")
    if not spreadsheet_id or not isinstance(ranges, list) or not ranges:
        raise ToolValidationError("sheets.values.batch_get requires spreadsheet_id and ranges[]")
    try:
        data = batch_get_values(token, str(spreadsheet_id), [str(r) for r in ranges])
    except GoogleSheetsAPIError as exc:
        raise _vendor_api_error(exc, "google_sheets") from exc
    return NormalizedResult(success=True, action="sheets.values.batch_get", connector_id=cid, data=data)


def _exec_docs_documents_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_docs import GoogleDocsAPIError, document_plain_text, get_document

    cid, token = _google_vendor_token(ctx, "google_docs", params)
    document_id = params.get("document_id") or params.get("documentId")
    if not document_id:
        raise ToolValidationError("docs.documents.get requires document_id")
    try:
        doc = get_document(token, str(document_id))
        text = document_plain_text(doc)
    except GoogleDocsAPIError as exc:
        raise _vendor_api_error(exc, "google_docs") from exc
    return NormalizedResult(
        success=True,
        action="docs.documents.get",
        connector_id=cid,
        data={"document": doc, "plain_text": text},
    )


def _exec_docs_documents_batch_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.google_docs import GoogleDocsAPIError, batch_get_documents, document_plain_text

    cid, token = _google_vendor_token(ctx, "google_docs", params)
    document_ids = params.get("document_ids") or params.get("documentIds")
    if not isinstance(document_ids, list) or not document_ids:
        raise ToolValidationError("docs.documents.batch_get requires document_ids[]")
    try:
        docs = batch_get_documents(token, [str(d) for d in document_ids])
    except GoogleDocsAPIError as exc:
        raise _vendor_api_error(exc, "google_docs") from exc
    return NormalizedResult(
        success=True,
        action="docs.documents.batch_get",
        connector_id=cid,
        data={
            "documents": [
                {"document": doc, "plain_text": document_plain_text(doc)} for doc in docs
            ]
        },
    )


_TOOL_REGISTRY: dict[str, ToolExecutor] = {
    "slack.post_message": _exec_slack_post_message,
    "slack.conversations.list": _exec_slack_conversations_list,
    "slack.conversations.history": _exec_slack_conversations_history,
    "slack.users.list": _exec_slack_users_list,
    "email.send": _exec_email_send,
    "email.messages.queue": _exec_email_messages_queue,
    "email.delivery.status": _exec_email_delivery_status,
    "email.send.template": _exec_email_send_template,
    "email.batch.send": _exec_email_batch_send,
    "webhook.post": _exec_webhook_post,
    "hubspot.contacts.get": _exec_hubspot_contacts_get,
    "hubspot.contacts.update": _exec_hubspot_contacts_update,
    "hubspot.notes.create": _exec_hubspot_notes_create,
    "hubspot.notes.delete": _exec_hubspot_notes_delete,
    "hubspot.deals.update_stage": _exec_hubspot_deals_update_stage,
    "hubspot.sequences.enroll": _exec_hubspot_sequences_enroll,
    "hubspot.contacts.create": _exec_hubspot_contacts_create,
    "hubspot.contacts.delete": _exec_hubspot_contacts_delete,
    "hubspot.contacts.search": _exec_hubspot_contacts_search,
    "hubspot.deals.get": _exec_hubspot_deals_get,
    "hubspot.deals.create": _exec_hubspot_deals_create,
    "hubspot.deals.delete": _exec_hubspot_deals_delete,
    "hubspot.deals.update": _exec_hubspot_deals_update,
    "hubspot.lists.add_contact": _exec_hubspot_lists_add_contact,
    "hubspot.companies.search": _exec_hubspot_companies_search,
    "hubspot.pipelines.list": _exec_hubspot_pipelines_list,
    "hubspot.tickets.create": _exec_hubspot_tickets_create,
    "salesforce.leads.get": _exec_salesforce_leads_get,
    "salesforce.leads.update": _exec_salesforce_leads_update,
    "salesforce.accounts.get": _exec_salesforce_accounts_get,
    "salesforce.opportunities.create": _exec_salesforce_opportunities_create,
    "salesforce.opportunities.update_stage": _exec_salesforce_opportunities_update_stage,
    "salesforce.tasks.create": _exec_salesforce_tasks_create,
    "salesforce.leads.create": _exec_salesforce_leads_create,
    "salesforce.leads.search": _exec_salesforce_leads_search,
    "salesforce.opportunities.get": _exec_salesforce_opportunities_get,
    "salesforce.opportunities.update": _exec_salesforce_opportunities_update,
    "salesforce.accounts.create": _exec_salesforce_accounts_create,
    "salesforce.accounts.update": _exec_salesforce_accounts_update,
    "quickbooks.invoices.list": _exec_quickbooks_invoices_list,
    "quickbooks.invoices.get": _exec_quickbooks_invoices_get,
    "quickbooks.payments.list": _exec_quickbooks_payments_list,
    "quickbooks.vendors.get": _exec_quickbooks_vendors_get,
    "quickbooks.customers.list": _exec_quickbooks_customers_list,
    "quickbooks.customers.get": _exec_quickbooks_customers_get,
    "quickbooks.customers.search": _exec_quickbooks_customers_search,
    "quickbooks.vendors.list": _exec_quickbooks_vendors_list,
    "quickbooks.accounts.list": _exec_quickbooks_accounts_list,
    "quickbooks.bills.list": _exec_quickbooks_bills_list,
    "quickbooks.bills.get": _exec_quickbooks_bills_get,
    "quickbooks.companyinfo.get": _exec_quickbooks_companyinfo_get,
    "quickbooks.invoices.create": _exec_quickbooks_invoices_create,
    "quickbooks.customers.create": _exec_quickbooks_customers_create,
    "quickbooks.payments.create": _exec_quickbooks_payments_create,
    "quickbooks.journalentries.create": _exec_quickbooks_journalentries_create,
    "stripe.invoices.list": _exec_stripe_invoices_list,
    "stripe.subscriptions.get": _exec_stripe_subscriptions_get,
    "pagerduty.incidents.acknowledge": _exec_pagerduty_incidents_acknowledge,
    "pagerduty.incidents.add_note": _exec_pagerduty_incidents_add_note,
    "pagerduty.incidents.escalate": _exec_pagerduty_incidents_escalate,
    "pagerduty.incidents.get": _exec_pagerduty_incidents_get,
    "pagerduty.incidents.list": _exec_pagerduty_incidents_list,
    "pagerduty.incidents.notes.list": _exec_pagerduty_incidents_notes_list,
    "pagerduty.incidents.resolve": _exec_pagerduty_incidents_resolve,
    "pagerduty.incidents.reassign": _exec_pagerduty_incidents_reassign,
    "pagerduty.services.list": _exec_pagerduty_services_list,
    "pagerduty.oncalls.list": _exec_pagerduty_oncalls_list,
    "jira.issues.create": _exec_jira_issues_create,
    "jira.issues.get": _exec_jira_issues_get,
    "jira.issues.search": _exec_jira_issues_search,
    "jira.issues.update": _exec_jira_issues_update,
    "jira.issues.assign": _exec_jira_issues_assign,
    "jira.issues.transition": _exec_jira_issues_transition,
    "jira.issues.transitions.list": _exec_jira_issues_transitions_list,
    "jira.issues.comment": _exec_jira_issues_comment,
    "jira.projects.list": _exec_jira_projects_list,
    "jira.users.search": _exec_jira_users_search,
    "zendesk.tickets.get": _exec_zendesk_tickets_get,
    "zendesk.tickets.create": _exec_zendesk_tickets_create,
    "zendesk.tickets.close": _exec_zendesk_tickets_close,
    "zendesk.tickets.update": _exec_zendesk_tickets_update,
    "zendesk.tickets.add_tags": _exec_zendesk_tickets_add_tags,
    "zendesk.tickets.list": _exec_zendesk_tickets_list,
    "zendesk.users.get": _exec_zendesk_users_get,
    "microsoft365.users.get": _exec_microsoft365_users_get,
    "microsoft365.mail.messages.list": _exec_microsoft365_mail_messages_list,
    "microsoft365.calendar.events.list": _exec_microsoft365_calendar_events_list,
    "github.pulls.list": _exec_github_pulls_list,
    "github.issues.get": _exec_github_issues_get,
    "github.repos.get": _exec_github_repos_get,
    "github.issues.create": _exec_github_issues_create,
    "github.issues.comment": _exec_github_issues_comment,
    "github.pulls.request_reviewer": _exec_github_pulls_request_reviewer,
    "github.actions.dispatch": _exec_github_actions_dispatch,
    "github.pulls.merge": _exec_github_pulls_merge,
    "github.releases.create": _exec_github_releases_create,
    "github.issues.list": _exec_github_issues_list,
    "github.pulls.get": _exec_github_pulls_get,
    "github.pulls.close": _exec_github_pulls_close,
    "calendar.freebusy": _exec_calendar_freebusy,
    "calendar.events.create": _exec_calendar_events_create,
    "calendar.events.list": _exec_calendar_events_list,
    "calendar.calendars.list": _exec_calendar_calendars_list,
    "analytics.properties.list": _exec_analytics_properties_list,
    "analytics.reports.run": _exec_analytics_reports_run,
    "analytics.metadata.list": _exec_analytics_metadata_list,
    "gmail.messages.list": _exec_gmail_messages_list,
    "gmail.messages.get": _exec_gmail_messages_get,
    "gmail.messages.send": _exec_gmail_messages_send,
    "gmail.labels.list": _exec_gmail_labels_list,
    "drive.files.list": _exec_drive_files_list,
    "drive.files.get": _exec_drive_files_get,
    "drive.permissions.list": _exec_drive_permissions_list,
    "sheets.spreadsheets.get": _exec_sheets_spreadsheets_get,
    "sheets.values.get": _exec_sheets_values_get,
    "sheets.values.batch_get": _exec_sheets_values_batch_get,
    "docs.documents.get": _exec_docs_documents_get,
    "docs.documents.batch_get": _exec_docs_documents_batch_get,
}

from app.services.linkedin_tools import LINKEDIN_TOOL_EXECUTORS
from app.services.marketo_tools import TOOL_EXECUTORS as MARKETO_TOOL_EXECUTORS
from app.services.netsuite_tools import NETSUITE_TOOL_EXECUTORS
from app.services.segment_tools import TOOL_EXECUTORS as SEGMENT_TOOL_EXECUTORS
from app.services.workday_tools import WORKDAY_TOOL_EXECUTORS
from app.services.xero_tools import XERO_TOOL_EXECUTORS
from app.services.bamboohr_tools import BAMBOOHR_TOOL_EXECUTORS
from app.services.fhir_tools import FHIR_TOOL_EXECUTORS
from app.services.clio_tools import CLIO_TOOL_EXECUTORS
from app.services.real_estate_tools import REAL_ESTATE_TOOL_EXECUTORS
from app.services.greenhouse_tools import GREENHOUSE_TOOL_EXECUTORS
from app.services.constant_contact_tools import CONSTANT_CONTACT_TOOL_EXECUTORS
from app.services.clickup_tools import CLICKUP_TOOL_EXECUTORS
from app.services.intercom_tools import INTERCOM_TOOL_EXECUTORS
from app.services.asana_tools import ASANA_TOOL_EXECUTORS
from app.services.monday_tools import MONDAY_TOOL_EXECUTORS
from app.services.odoo_tools import ODOO_TOOL_EXECUTORS
from app.services.canva_tools import CANVA_TOOL_EXECUTORS
from app.services.figma_tools import FIGMA_TOOL_EXECUTORS

_TOOL_REGISTRY.update(NETSUITE_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(WORKDAY_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(MARKETO_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(SEGMENT_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(LINKEDIN_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(XERO_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(BAMBOOHR_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(FHIR_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(CLIO_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(REAL_ESTATE_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(GREENHOUSE_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(CONSTANT_CONTACT_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(CLICKUP_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(INTERCOM_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(ASANA_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(MONDAY_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(ODOO_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(CANVA_TOOL_EXECUTORS)
_TOOL_REGISTRY.update(FIGMA_TOOL_EXECUTORS)

from app.services.priority_connector_tools import PRIORITY_CONNECTOR_TOOLS
from app.connectors.catalog_http.registry import build_catalog_http_executors

_TOOL_REGISTRY.update(PRIORITY_CONNECTOR_TOOLS)
_TOOL_REGISTRY.update(build_catalog_http_executors(skip=set(_TOOL_REGISTRY.keys())))

# Workflow step type → canonical tool action
STEP_TYPE_TO_ACTION: dict[str, str] = {
    "slack_post_message": "slack.post_message",
    "email_send": "email.send",
    "webhook_post": "webhook.post",
}


def _resolve_tool_executor(action: str, ctx: ToolContext | None = None) -> ToolExecutor | None:
    """Resolve built-in, org-private sandbox, or public partner tool executor."""
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action

    resolved = resolve_registry_action(action, set(_TOOL_REGISTRY.keys()))
    executor = _TOOL_REGISTRY.get(resolved)
    if executor:
        return executor
    if ctx and ctx.client and ctx.org_id and ctx.settings.private_connector_runtime_enabled:
        vendor = action.split(".", 1)[0] if "." in action else ""
        if vendor:
            from app.connectors.private.runtime import make_private_executor
            from app.connectors.sdk.manifest import parse_manifest
            from app.services.private_connector_bundle_service import (
                ensure_private_scopes_registered,
                get_active_bundle_for_vendor,
            )

            bundle = get_active_bundle_for_vendor(ctx.client, ctx.org_id, vendor)
            if bundle:
                sources = bundle.get("package_sources") or {}
                handler_source = sources.get("handlers.py") if isinstance(sources, dict) else None
                if handler_source:
                    ensure_private_scopes_registered(parse_manifest(bundle.get("manifest") or {}))
                    return make_private_executor(handler_source, action, ctx.settings)
    from app.connectors.sdk.registry import get_partner_executor

    return get_partner_executor(action)


def list_registered_actions() -> list[str]:
    from app.connectors.sdk.registry import list_partner_actions

    return sorted(set(_TOOL_REGISTRY.keys()) | set(list_partner_actions()))


def invoke_tool(ctx: ToolContext, action: str, params: dict[str, Any] | None = None) -> NormalizedResult:
    """Invoke a registered connector tool with audit, rate limits, retries, and agent permissions."""
    from dataclasses import replace

    params = dict(params or {})
    federation_token = params.pop("federation_token", None) or params.pop("federationToken", None)
    federation_grant_id = params.pop("federation_grant_id", None) or params.pop("federationGrantId", None)
    federated_grant = None
    if federation_token or federation_grant_id:
        from app.services.federated_connector_service import (
            FederatedConnectorError,
            resolve_federated_tool_context,
        )

        try:
            federated_grant = resolve_federated_tool_context(
                ctx.client,
                grantee_org_id=ctx.org_id,
                action=action,
                federation_token=str(federation_token) if federation_token else None,
                federation_grant_id=str(federation_grant_id) if federation_grant_id else None,
            )
        except FederatedConnectorError as exc:
            raise ToolValidationError(str(exc), code=exc.code) from exc
        params["connector_id"] = federated_grant.connector_id
        ctx = replace(
            ctx,
            org_id=federated_grant.grantor_org_id,
            connector_id=federated_grant.connector_id,
        )
    if ctx.run_id:
        from app.services.agent_interrupt_service import AgentExecutionInterrupted, enforce_interrupt

        try:
            enforce_interrupt(ctx.client, ctx.org_id, "workflow_run", str(ctx.run_id), actor_id=ctx.actor_id)
        except AgentExecutionInterrupted as exc:
            raise ToolValidationError(f"Execution interrupted ({exc.signal})") from exc
    if ctx.task_id:
        from app.services.agent_interrupt_service import AgentExecutionInterrupted, enforce_interrupt

        try:
            enforce_interrupt(ctx.client, ctx.org_id, "agent_job", str(ctx.task_id), actor_id=ctx.actor_id)
        except AgentExecutionInterrupted as exc:
            raise ToolValidationError(f"Execution interrupted ({exc.signal})") from exc
    if ctx.operator_id:
        from app.services.autonomous_budget_service import AutonomousBudgetExceededError, enforce_autonomous_tool_budget

        try:
            enforce_autonomous_tool_budget(
                ctx.client,
                ctx.org_id,
                str(ctx.operator_id),
                actor_id=ctx.actor_id or None,
            )
        except AutonomousBudgetExceededError as exc:
            raise ToolValidationError(str(exc), code=exc.code) from exc

    executor = _resolve_tool_executor(action, ctx)
    if not executor:
        raise ToolNotFoundError(f"Unknown tool action: {action}")

    connector_id = params.get("connector_id") or ctx.connector_id
    connector_type = action.split(".", 1)[0] if "." in action else action
    cid = str(connector_id) if connector_id else None
    try:
        from app.services.hipaa_service import HipaaComplianceError, enforce_hipaa_for_tool_invoke

        enforce_hipaa_for_tool_invoke(ctx.client, ctx.org_id, action, cid)
    except HipaaComplianceError as exc:
        _write_tool_audit(
            ctx,
            action,
            cid,
            "tool.invoke.failed",
            {"error_code": exc.code, "error": str(exc)[:200]},
        )
        raise ToolValidationError(str(exc), code=exc.code) from exc
    if federated_grant is None:
        try:
            assert_agent_tool_permission(ctx, action, cid, connector_type)
        except ToolPermissionDeniedError as exc:
            _write_tool_audit(
                ctx,
                action,
                cid,
                "tool.invoke.failed",
                {"error_code": exc.code, "error": str(exc)[:200]},
            )
            return NormalizedResult(
                success=False,
                action=action,
                error_code=exc.code,
                error_message=str(exc),
                connector_id=cid,
            )
    _write_tool_audit(ctx, action, cid, "tool.invoke.requested")

    compensation_snapshot = None
    if ctx.run_id:
        from app.services.compensation_service import prepare_forward_snapshot, record_compensatable_action, should_track_compensation

        if should_track_compensation(ctx, action):
            compensation_snapshot = prepare_forward_snapshot(ctx, action, params)

    last_error: ToolError | None = None
    attempts = _MAX_RETRIES + 1
    for attempt in range(attempts):
        started = time.perf_counter()
        try:
            result = executor(ctx, params)
            result.latency_ms = result.latency_ms or int((time.perf_counter() - started) * 1000)
            _write_tool_audit(
                ctx,
                action,
                result.connector_id,
                "tool.invoke.completed",
                {"latency_ms": result.latency_ms, "attempt": attempt + 1},
            )
            if federated_grant:
                from app.services.federated_connector_service import audit_federated_tool_invoke

                audit_federated_tool_invoke(
                    ctx.client,
                    grant=federated_grant,
                    action=action,
                    actor_id=ctx.actor_id,
                    success=True,
                )
            if ctx.transparency_log_id:
                try:
                    from app.services.transparency_service import append_tool_invocation

                    append_tool_invocation(
                        ctx.client,
                        org_id=ctx.org_id,
                        log_id=ctx.transparency_log_id,
                        action=action,
                        connector_id=result.connector_id or cid,
                        success=True,
                        latency_ms=result.latency_ms,
                    )
                except Exception:
                    pass
            try:
                from app.services.marketplace_billing_service import (
                    build_invoke_idempotency_key,
                    record_marketplace_usage_for_invoke,
                )

                record_marketplace_usage_for_invoke(
                    ctx.client,
                    ctx.settings,
                    customer_org_id=ctx.org_id,
                    connector_id=result.connector_id or cid,
                    vendor=connector_type,
                    action=action,
                    idempotency_key=build_invoke_idempotency_key(ctx, action, result.connector_id or cid),
                )
            except Exception:
                pass
            if ctx.run_id:
                from app.services.compensation_service import record_compensatable_action, should_track_compensation

                if should_track_compensation(ctx, action):
                    record_compensatable_action(
                        ctx.client,
                        org_id=ctx.org_id,
                        run_id=str(ctx.run_id),
                        step_id=ctx.step_id,
                        forward_action=action,
                        forward_params=params,
                        forward_result=result.data,
                        connector_id=result.connector_id or cid,
                        snapshot=compensation_snapshot,
                    )
            return result
        except Exception as exc:
            tool_exc = _classify_error(exc)
            last_error = tool_exc
            retryable = isinstance(tool_exc, ToolRateLimitedError) or (
                not isinstance(tool_exc, (ToolValidationError, ToolAuthExpiredError, ToolNotFoundError))
                and attempt < attempts - 1
            )
            if not retryable:
                break
            if attempt < len(_RETRY_BACKOFF_SEC):
                time.sleep(_RETRY_BACKOFF_SEC[attempt])

    assert last_error is not None
    _write_tool_audit(
        ctx,
        action,
        str(connector_id) if connector_id else None,
        "tool.invoke.failed",
        {"error_code": last_error.code, "error": str(last_error)[:200]},
    )
    if ctx.transparency_log_id:
        try:
            from app.services.transparency_service import append_tool_invocation

            append_tool_invocation(
                ctx.client,
                org_id=ctx.org_id,
                log_id=ctx.transparency_log_id,
                action=action,
                connector_id=str(connector_id) if connector_id else None,
                success=False,
                error_code=last_error.code,
            )
        except Exception:
            pass
    return NormalizedResult(
        success=False,
        action=action,
        error_code=last_error.code,
        error_message=str(last_error),
        connector_id=str(connector_id) if connector_id else None,
    )


def tool_context_from_step(context: Any) -> ToolContext:
    """Build ToolContext from workflows StepContext."""
    params = context.parameters if isinstance(context.parameters, dict) else {}
    operator_id = None
    transparency_log_id = None
    if params.get("_transparency_log_id"):
        transparency_log_id = str(params["_transparency_log_id"])
    if params.get("_autonomous_run") and params.get("operator_id"):
        operator_id = str(params["operator_id"])
    return ToolContext(
        settings=context.settings,
        client=context.client,
        org_id=context.org_id,
        actor_id=context.user_id or "",
        environment_name=context.environment_name or "default",
        run_id=context.run_id,
        step_id=context.step_id,
        step_type=context.step_type,
        operator_id=operator_id,
        transparency_log_id=transparency_log_id,
        connector_id=(context.config or {}).get("connector_id"),
    )


def _resolve_param_source(
    spec: Any,
    parameters: dict[str, Any],
    step_outputs: dict[str, Any] | None,
) -> Any:
    if isinstance(spec, dict) and spec.get("from_step"):
        step_id = str(spec["from_step"])
        path = spec.get("path") or []
        output = (step_outputs or {}).get(step_id) or {}
        value: Any = output
        for key in path:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value
    if isinstance(spec, str) and spec.startswith("$"):
        return parameters.get(spec[1:])
    return spec


def params_for_step(
    step_type: str,
    config: dict[str, Any],
    parameters: dict[str, Any],
    *,
    step_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map workflow step config + parameters to invoke_tool params."""
    cfg = config or {}
    params = dict(parameters)
    if cfg.get("connector_id"):
        params["connector_id"] = cfg["connector_id"]
    if step_type == "invoke_tool":
        sources = cfg.get("param_sources") or cfg.get("params") or {}
        if isinstance(sources, dict):
            for key, spec in sources.items():
                resolved = _resolve_param_source(spec, parameters, step_outputs)
                if resolved is not None and resolved != "":
                    params[key] = resolved
    if step_type == "slack_post_message":
        msg_key = cfg.get("message_input_key", "message")
        message = parameters.get(msg_key, parameters.get("message", ""))
        if cfg.get("message_from_step"):
            resolved = _resolve_param_source(cfg["message_from_step"], parameters, step_outputs)
            if resolved is not None and resolved != "":
                message = resolved
        params["message"] = message
        params["channel"] = cfg.get("channel") or parameters.get("channel", "")
    elif step_type == "email_send":
        params["to"] = parameters.get(cfg.get("to_input_key", "to"), "")
        params["subject"] = parameters.get(cfg.get("subject_input_key", "subject"), "")
        params["body"] = parameters.get(cfg.get("body_input_key", "body"), "")
        params["content_type"] = cfg.get("content_type", "text/plain")
    elif step_type == "webhook_post":
        payload_key = cfg.get("payload_input_key", "payload")
        params["payload"] = parameters.get(payload_key)
        params["path"] = cfg.get("path")
        params["headers"] = cfg.get("headers") or {}
    return params
