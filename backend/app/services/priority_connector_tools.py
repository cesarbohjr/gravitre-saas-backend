"""Priority vendor tool executors (Slack, M365, Google, Zendesk v2/v3)."""
from __future__ import annotations

from typing import Any

from app.connectors.connector_tool_auth import resolve_slack_bot_token
from app.connectors.microsoft365 import (
    Microsoft365APIError,
    batch_send_mail,
    create_calendar_event,
    post_teams_channel_message,
    send_mail,
    update_excel_range,
    upload_drive_file,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.connectors.slack import (
    add_reaction,
    create_conversation,
    trigger_workflow,
    update_message,
    upload_file,
)
from app.connectors.zendesk import (
    ZendeskAPIError,
    apply_macro,
    create_side_conversation,
    merge_tickets,
)
from app.connectors.connector_tool_auth import resolve_microsoft365_access_token, resolve_zendesk_auth
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolChannelNotFoundError,
    ToolConnectorNotConnectedError,
    ToolContext,
    ToolError,
    ToolMissingScopeError,
    ToolValidationError,
)

ToolExecutor = Any


def _vendor_api_error(exc: Exception, vendor: str) -> ToolError:
    msg = str(exc)
    lower = msg.lower()
    if "channel_not_found" in lower or "not_in_channel" in lower:
        return ToolChannelNotFoundError(msg)
    if "missing_scope" in lower or "insufficient scope" in lower or "required scope" in lower:
        return ToolMissingScopeError(msg)
    if "no active" in lower and "connector" in lower:
        return ToolConnectorNotConnectedError(msg)
    if hasattr(exc, "status_code") and getattr(exc, "status_code") in {401, 403}:
        return ToolAuthExpiredError(msg)
    return ToolValidationError(msg)


def _connector_by_type(ctx: ToolContext, connector_type: str, params: dict[str, Any]) -> dict[str, Any]:
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, connector_type, environment_name=ctx.environment_name)
    if not conn:
        raise ToolConnectorNotConnectedError(f"No active {connector_type} connector found for org")
    return conn


def _slack_connector_and_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    conn = _connector_by_type(ctx, "slack", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "slack", "slack", cid)
    token = resolve_slack_bot_token(ctx.client, ctx.org_id, cid, ctx.settings)
    if not token:
        raise ToolAuthExpiredError("Slack OAuth not connected")
    return cid, token


def _microsoft365_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    conn = _connector_by_type(ctx, "microsoft365", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "microsoft365", "microsoft365", cid)
    token = resolve_microsoft365_access_token(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ToolAuthExpiredError("Microsoft 365 OAuth not connected")
    return cid, token


def _zendesk_credentials(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str | None, str | None, str | None]:
    conn = _connector_by_type(ctx, "zendesk", params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "zendesk", "zendesk", cid)
    subdomain, email, token, oauth = resolve_zendesk_auth(
        ctx.client, ctx.org_id, conn, ctx.settings, environment_name=ctx.environment_name
    )
    return cid, subdomain, email, token, oauth


def _google_token(ctx: ToolContext, vendor: str, params: dict[str, Any]) -> tuple[str, str]:
    from app.connectors.google_vendor_oauth import ensure_google_vendor_session

    conn = _connector_by_type(ctx, vendor, params)
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, vendor, vendor, cid)
    oauth_token, oauth_err = ensure_google_vendor_session(
        ctx.client, ctx.org_id, cid, ctx.settings, vendor=vendor, environment_name=ctx.environment_name
    )
    if oauth_err or not oauth_token:
        raise ToolAuthExpiredError(oauth_err or f"{vendor} OAuth not connected")
    return cid, oauth_token


def _exec_slack_conversations_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    name = params.get("name")
    if not name:
        raise ToolValidationError("slack.conversations.create requires name")
    try:
        data = create_conversation(token, str(name), is_private=bool(params.get("is_private")))
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(success=True, action="slack.conversations.create", connector_id=cid, data=data)


def _exec_slack_chat_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    channel = params.get("channel")
    ts = params.get("ts") or params.get("timestamp")
    text = params.get("text")
    if not channel or not ts or not text:
        raise ToolValidationError("slack.chat.update requires channel, ts, text")
    try:
        data = update_message(token, str(channel), str(ts), str(text))
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(success=True, action="slack.chat.update", connector_id=cid, data=data)


def _exec_slack_files_upload(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    try:
        data = upload_file(
            token,
            channels=params.get("channels") or params.get("channel"),
            content=params.get("content"),
            filename=params.get("filename"),
            initial_comment=params.get("initial_comment"),
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(success=True, action="slack.files.upload", connector_id=cid, data=data)


def _exec_slack_reactions_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    channel = params.get("channel")
    timestamp = params.get("timestamp") or params.get("ts")
    name = params.get("name") or params.get("emoji")
    if not channel or not timestamp or not name:
        raise ToolValidationError("slack.reactions.add requires channel, timestamp, name")
    try:
        data = add_reaction(token, str(channel), str(timestamp), str(name))
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(success=True, action="slack.reactions.add", connector_id=cid, data=data)


def _exec_slack_workflows_trigger(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _slack_connector_and_token(ctx, params)
    try:
        data = trigger_workflow(
            token,
            trigger_id=params.get("trigger_id"),
            workflow=params.get("workflow"),
            inputs=params.get("inputs") if isinstance(params.get("inputs"), dict) else None,
        )
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return NormalizedResult(success=True, action="slack.workflows.trigger", connector_id=cid, data=data)


def _exec_m365_mail_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    to_recipients = params.get("to") or params.get("to_recipients")
    if isinstance(to_recipients, str):
        to_recipients = [to_recipients]
    subject = str(params.get("subject") or "")
    body = str(params.get("body") or "")
    recipients = [str(x) for x in (to_recipients or [])]
    try:
        data = send_mail(
            token,
            subject=subject,
            body=body,
            to_recipients=recipients,
        )
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    # Graph sendMail often returns empty 202 — stamp accepted proof (STA-337).
    if not isinstance(data, dict) or not data:
        data = {}
    else:
        data = dict(data)
    if not data.get("result_url") and not data.get("id"):
        data.setdefault("accepted_async", True)
        data.setdefault("outcome_effect", "accepted_async")
        data.setdefault("status", "accepted")
        data["result_url"] = "https://outlook.office.com/mail/"
        data["subject"] = subject
        data["to_recipients"] = recipients
    return NormalizedResult(success=True, action="microsoft365.mail.send", connector_id=cid, data=data)


def _exec_m365_calendar_events_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    try:
        data = create_calendar_event(
            token,
            subject=str(params.get("subject") or params.get("title") or ""),
            start_datetime=str(params.get("start") or params.get("start_datetime") or ""),
            end_datetime=str(params.get("end") or params.get("end_datetime") or ""),
            body=params.get("body"),
        )
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(success=True, action="microsoft365.calendar.events.create", connector_id=cid, data=data)


def _exec_m365_files_upload(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    filename = params.get("filename") or params.get("name")
    content = params.get("content")
    if not filename or content is None:
        raise ToolValidationError("microsoft365.files.upload requires filename and content")
    try:
        data = upload_drive_file(token, filename=str(filename), content=content, parent_id=params.get("parent_id"))
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(success=True, action="microsoft365.files.upload", connector_id=cid, data=data)


def _exec_m365_excel_workbook_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    item_id = params.get("item_id") or params.get("file_id")
    worksheet = params.get("worksheet") or params.get("sheet")
    address = params.get("address") or params.get("range")
    values = params.get("values")
    if not item_id or not worksheet or not address or not isinstance(values, list):
        raise ToolValidationError("microsoft365.excel.workbook.update requires item_id, worksheet, address, values")
    try:
        data = update_excel_range(token, item_id=str(item_id), worksheet=str(worksheet), address=str(address), values=values)
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(success=True, action="microsoft365.excel.workbook.update", connector_id=cid, data=data)


def _exec_m365_teams_notify(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    team_id = params.get("team_id")
    channel_id = params.get("channel_id")
    content = params.get("content") or params.get("text")
    if not team_id or not channel_id or not content:
        raise ToolValidationError("microsoft365.teams.notify requires team_id, channel_id, content")
    try:
        data = post_teams_channel_message(token, team_id=str(team_id), channel_id=str(channel_id), content=str(content))
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(success=True, action="microsoft365.teams.notify", connector_id=cid, data=data)


def _exec_m365_batch_mail(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _microsoft365_token(ctx, params)
    messages = params.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ToolValidationError("microsoft365.batch.mail requires messages[]")
    try:
        data = batch_send_mail(token, messages=messages)
    except Microsoft365APIError as exc:
        raise _vendor_api_error(exc, "microsoft365") from exc
    return NormalizedResult(success=True, action="microsoft365.batch.mail", connector_id=cid, data=data)


def _exec_zendesk_tickets_merge(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth = _zendesk_credentials(ctx, params)
    target = params.get("target_ticket_id") or params.get("ticket_id")
    sources = params.get("source_ticket_ids") or params.get("ids")
    if not target or not isinstance(sources, list):
        raise ToolValidationError("zendesk.tickets.merge requires target_ticket_id and source_ticket_ids[]")
    try:
        data = merge_tickets(subdomain, email, token, target, source_ticket_ids=sources, oauth_access_token=oauth)
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.tickets.merge", connector_id=cid, data=data)


def _exec_zendesk_macros_apply(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id")
    macro_id = params.get("macro_id")
    if not ticket_id or not macro_id:
        raise ToolValidationError("zendesk.macros.apply requires ticket_id and macro_id")
    try:
        data = apply_macro(subdomain, email, token, ticket_id, macro_id, oauth_access_token=oauth)
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.macros.apply", connector_id=cid, data=data)


def _exec_zendesk_side_conversations_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, subdomain, email, token, oauth = _zendesk_credentials(ctx, params)
    ticket_id = params.get("ticket_id")
    subject = params.get("subject")
    body = params.get("body")
    if not ticket_id or not subject or not body:
        raise ToolValidationError("zendesk.side_conversations.create requires ticket_id, subject, body")
    try:
        data = create_side_conversation(
            subdomain,
            email,
            token,
            ticket_id,
            subject=str(subject),
            body=str(body),
            to_emails=params.get("to_emails") if isinstance(params.get("to_emails"), list) else None,
            oauth_access_token=oauth,
        )
    except ZendeskAPIError as exc:
        raise _vendor_api_error(exc, "zendesk") from exc
    return NormalizedResult(success=True, action="zendesk.side_conversations.create", connector_id=cid, data=data)


def _google_exec(vendor: str, registry_action: str, fn):
    def _exec(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        cid, token = _google_token(ctx, vendor, params)
        try:
            data = fn(token, params)
        except Exception as exc:
            raise _vendor_api_error(exc, vendor) from exc
        return NormalizedResult(success=True, action=registry_action, connector_id=cid, data=data if isinstance(data, dict) else {"result": data})

    return _exec


def _calendar_update(token, params):
    from app.connectors.google_calendar import update_event

    return {
        "event": update_event(
            token,
            calendar_id=str(params.get("calendar_id") or "primary"),
            event_id=str(params.get("event_id") or params.get("id") or ""),
            patch=params.get("patch") or params,
        )
    }


def _calendar_delete(token, params):
    from app.connectors.google_calendar import delete_event

    delete_event(
        token,
        calendar_id=str(params.get("calendar_id") or "primary"),
        event_id=str(params.get("event_id") or params.get("id") or ""),
    )
    return {"deleted": True}


def _calendar_quick_add(token, params):
    from app.connectors.google_calendar import quick_add_event

    return {"event": quick_add_event(token, calendar_id=str(params.get("calendar_id") or "primary"), text=str(params.get("text") or ""))}


def _calendar_acl(token, params):
    from app.connectors.google_calendar import list_acl

    return list_acl(token, calendar_id=str(params.get("calendar_id") or "primary"))


def _calendar_batch(token, params):
    from app.connectors.google_calendar import batch_events

    return batch_events(token, requests=params.get("requests") or [])


def _gmail_draft(token, params):
    from app.connectors.gmail import create_draft

    return {"draft": create_draft(token, to=str(params.get("to") or ""), subject=str(params.get("subject") or ""), body=str(params.get("body") or ""))}


def _gmail_label(token, params):
    from app.connectors.gmail import create_label

    return create_label(token, name=str(params.get("name") or ""))


def _gmail_thread(token, params):
    from app.connectors.gmail import modify_thread

    return modify_thread(
        token,
        thread_id=str(params.get("thread_id") or ""),
        add_label_ids=params.get("add_label_ids"),
        remove_label_ids=params.get("remove_label_ids"),
    )


def _gmail_batch(token, params):
    from app.connectors.gmail import batch_get_messages

    ids = params.get("message_ids") or params.get("ids") or []
    return {"messages": batch_get_messages(token, [str(i) for i in ids])}


def _gmail_watch(token, params):
    from app.connectors.gmail import create_watch

    return create_watch(token, topic_name=str(params.get("topic_name") or params.get("topic") or ""))


def _drive_create(token, params):
    from app.connectors.google_drive import create_file

    return create_file(token, name=str(params.get("name") or ""), content=params.get("content"), mime_type=str(params.get("mime_type") or "text/plain"))


def _drive_update(token, params):
    from app.connectors.google_drive import update_file

    return update_file(token, str(params.get("file_id") or ""), name=params.get("name"), description=params.get("description"))


def _drive_perm(token, params):
    from app.connectors.google_drive import create_permission

    return create_permission(token, str(params.get("file_id") or ""), role=str(params.get("role") or "reader"), email_address=params.get("email"))


def _drive_export(token, params):
    from app.connectors.google_drive import export_file
    import base64

    content = export_file(token, str(params.get("file_id") or ""), mime_type=str(params.get("mime_type") or "application/pdf"))
    return {"content_base64": base64.b64encode(content).decode()}


def _drive_changes(token, params):
    from app.connectors.google_drive import list_changes

    return list_changes(token, page_token=params.get("page_token"), page_size=int(params.get("page_size") or 25))


def _drive_batch_perm(token, params):
    from app.connectors.google_drive import batch_permissions

    return batch_permissions(token, requests=params.get("requests") or [])


def _sheets_update(token, params):
    from app.connectors.google_sheets import update_values

    return update_values(token, str(params.get("spreadsheet_id") or ""), str(params.get("range") or ""), params.get("values") or [])


def _sheets_append(token, params):
    from app.connectors.google_sheets import append_values

    return append_values(token, str(params.get("spreadsheet_id") or ""), str(params.get("range") or ""), params.get("values") or [])


def _sheets_create(token, params):
    from app.connectors.google_sheets import create_spreadsheet

    return create_spreadsheet(token, title=str(params.get("title") or "Untitled"))


def _sheets_batch_update(token, params):
    from app.connectors.google_sheets import batch_update_values

    return batch_update_values(token, str(params.get("spreadsheet_id") or ""), params.get("data") or [])


def _sheets_chart(token, params):
    from app.connectors.google_sheets import add_chart

    return add_chart(token, str(params.get("spreadsheet_id") or ""), sheet_id=int(params.get("sheet_id") or 0), chart_spec=params.get("chart_spec") or {})


def _sheets_pivot(token, params):
    from app.connectors.google_sheets import create_pivot_table

    return create_pivot_table(token, str(params.get("spreadsheet_id") or ""), pivot_spec=params.get("pivot_spec") or {})


def _docs_create(token, params):
    from app.connectors.google_docs import create_document

    return create_document(token, title=str(params.get("title") or "Untitled"))


def _docs_batch_update(token, params):
    from app.connectors.google_docs import batch_update_document

    return batch_update_document(token, str(params.get("document_id") or ""), params.get("requests") or [])


def _docs_replace(token, params):
    from app.connectors.google_docs import replace_text

    return replace_text(token, str(params.get("document_id") or ""), find_text=str(params.get("find") or ""), replace_text_value=str(params.get("replace") or ""))


def _docs_table(token, params):
    from app.connectors.google_docs import insert_table

    return insert_table(token, str(params.get("document_id") or ""), rows=int(params.get("rows") or 2), columns=int(params.get("columns") or 2))


def _docs_pdf(token, params):
    from app.connectors.google_docs import export_pdf
    import base64

    content = export_pdf(token, str(params.get("document_id") or ""))
    return {"content_base64": base64.b64encode(content).decode()}


def _analytics_audience(token, params):
    from app.connectors.google_analytics import create_audience

    return create_audience(token, str(params.get("property_id") or ""), display_name=str(params.get("display_name") or params.get("name") or ""))


def _analytics_conversion(token, params):
    from app.connectors.google_analytics import create_conversion

    return create_conversion(token, str(params.get("property_id") or ""), event_name=str(params.get("event_name") or ""))


def _analytics_batch(token, params):
    from app.connectors.google_analytics import batch_run_reports

    return batch_run_reports(token, str(params.get("property_id") or ""), requests=params.get("requests") or [])


def _analytics_realtime(token, params):
    from app.connectors.google_analytics import run_realtime_report

    return run_realtime_report(token, str(params.get("property_id") or ""))


def _alias(action: str, executor: ToolExecutor) -> dict[str, ToolExecutor]:
    from app.connectors.action_catalog.tool_aliases import registry_keys_for_catalog_tool

    out = {action: executor}
    for key in registry_keys_for_catalog_tool(action):
        out[key] = executor
    return out


PRIORITY_CONNECTOR_TOOLS: dict[str, ToolExecutor] = {}
PRIORITY_CONNECTOR_TOOLS.update(
    {
        "slack.conversations.create": _exec_slack_conversations_create,
        "slack.chat.update": _exec_slack_chat_update,
        "slack.files.upload": _exec_slack_files_upload,
        "slack.reactions.add": _exec_slack_reactions_add,
        "slack.workflows.trigger": _exec_slack_workflows_trigger,
        "microsoft365.mail.send": _exec_m365_mail_send,
        "microsoft365.calendar.events.create": _exec_m365_calendar_events_create,
        "microsoft365.files.upload": _exec_m365_files_upload,
        "microsoft365.excel.workbook.update": _exec_m365_excel_workbook_update,
        "microsoft365.teams.notify": _exec_m365_teams_notify,
        "microsoft365.batch.mail": _exec_m365_batch_mail,
        "zendesk.tickets.merge": _exec_zendesk_tickets_merge,
        "zendesk.macros.apply": _exec_zendesk_macros_apply,
        "zendesk.side_conversations.create": _exec_zendesk_side_conversations_create,
    }
)

for catalog_action, fn in [
    ("google_calendar.events.update", _calendar_update),
    ("google_calendar.events.delete", _calendar_delete),
    ("google_calendar.events.quick_add", _calendar_quick_add),
    ("google_calendar.acl.list", _calendar_acl),
    ("google_calendar.batch.events", _calendar_batch),
    ("gmail.drafts.create", _gmail_draft),
    ("gmail.labels.create", _gmail_label),
    ("gmail.threads.modify", _gmail_thread),
    ("gmail.messages.batch", _gmail_batch),
    ("gmail.watch.create", _gmail_watch),
    ("google_drive.files.create", _drive_create),
    ("google_drive.files.update", _drive_update),
    ("google_drive.permissions.create", _drive_perm),
    ("google_drive.files.export", _drive_export),
    ("google_drive.changes.list", _drive_changes),
    ("google_drive.batch.permissions", _drive_batch_perm),
    ("google_sheets.values.update", _sheets_update),
    ("google_sheets.values.append", _sheets_append),
    ("google_sheets.spreadsheets.create", _sheets_create),
    ("google_sheets.values.batch_update", _sheets_batch_update),
    ("google_sheets.charts.add", _sheets_chart),
    ("google_sheets.pivot.create", _sheets_pivot),
    ("google_docs.documents.create", _docs_create),
    ("google_docs.documents.batch_update", _docs_batch_update),
    ("google_docs.documents.replace_text", _docs_replace),
    ("google_docs.documents.insert_table", _docs_table),
    ("google_docs.export.pdf", _docs_pdf),
    ("google_analytics.audiences.create", _analytics_audience),
    ("google_analytics.conversions.create", _analytics_conversion),
    ("google_analytics.reports.batch", _analytics_batch),
    ("google_analytics.realtime.run", _analytics_realtime),
]:
    vendor = catalog_action.split(".", 1)[0]
    exec_fn = _google_exec(vendor, catalog_action, fn)
    PRIORITY_CONNECTOR_TOOLS.update(_alias(catalog_action, exec_fn))
