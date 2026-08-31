"""Hand-verified api_reference entries the static extractor cannot transcribe.

Every entry here was produced by reading the cited source line, not by pattern
matching or by inferring from the action's name. Two situations land here:

1. The endpoint is real but unreachable to static analysis — a vendor SDK call
   (Stripe), or a path assembled by a helper function rather than a literal.
2. There genuinely is no vendor endpoint. A locally-computed checklist, an SMTP
   send, a customer-configured webhook target, or a catalog entry with no
   executor at all. These are recorded as such rather than given a
   plausible-looking URL, because a wrong endpoint here would silently corrupt
   the drift scan this mapping exists to enable.

``kind`` values:
  rest             real HTTP endpoint, confirmed by reading the implementation
  sdk              real HTTP endpoint issued by a vendor SDK, not by our code
  smtp             SMTP protocol, no HTTP endpoint exists
  local            computed in-process, no vendor call at all
  caller_supplied  URL comes from connector config / caller input at runtime
  browser_agent    driven through a browser, not a documented vendor API
  unregistered     catalog entry with no executor — cannot be invoked
"""
from __future__ import annotations

from dataclasses import dataclass

REVIEWED = "2026-08-29"


@dataclass(frozen=True)
class ManualApiReference:
    kind: str
    source: str
    note: str
    method: str | None = None
    path: str | None = None
    base_url: str | None = None

    @property
    def api_reference(self) -> str | None:
        if self.method and self.path:
            return f"{self.method} {self.path}"
        return None


MANUAL_API_REFERENCES: dict[str, ManualApiReference] = {
    # ---- real endpoints the extractor cannot see -------------------------
    "cisa_kev.feed.get": ManualApiReference(
        kind="rest",
        method="GET",
        path="/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        base_url="https://www.cisa.gov",
        source="backend/app/intelligence_packs/msp/__init__.py:74",
        note="Static JSON feed. URL is overridable via CISA_KEV_URL env var.",
    ),
    "microsoft365.users.get": ManualApiReference(
        kind="rest",
        method="GET",
        path="/users/{user_id}",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py:65 (path from _graph_user_root, line 19)",
        note="Path is built by _graph_user_root(): '/me' for the signed-in user, "
        "'/users/{user_id}' for a directory id — so it is not a literal.",
    ),
    # _graph_user_root() returns "/me" for the signed-in user and
    # "/users/{user_id}" for a directory id, so the root is not a literal. "/me"
    # is the default (no user_id supplied) and is what these actions send unless
    # a caller names a directory user.
    "microsoft365.calendar.events.list": ManualApiReference(
        kind="rest",
        method="GET",
        path="/me/calendar/events",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Becomes /users/{user_id}/calendar/events when a directory user id is given.",
    ),
    "microsoft365.calendar.events.create": ManualApiReference(
        kind="rest",
        method="POST",
        path="/me/calendar/events",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Becomes /users/{user_id}/calendar/events when a directory user id is given.",
    ),
    "microsoft365.mail.messages.list": ManualApiReference(
        kind="rest",
        method="GET",
        path="/me/messages",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Becomes /users/{user_id}/messages when a directory user id is given.",
    ),
    "microsoft365.mail.send": ManualApiReference(
        kind="rest",
        method="POST",
        path="/me/sendMail",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Becomes /users/{user_id}/sendMail when a directory user id is given.",
    ),
    "microsoft365.excel.workbook.update": ManualApiReference(
        kind="rest",
        method="PATCH",
        path="/me/drive/items/{item_id}/workbook/worksheets/{worksheet}/range(address='{address}')",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Becomes /users/{user_id}/drive/... when a directory user id is given.",
    ),
    "outlook.messages.list": ManualApiReference(
        kind="rest",
        method="GET",
        path="/me/messages",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Outlook actions share the Microsoft Graph mail implementation.",
    ),
    "outlook.messages.send": ManualApiReference(
        kind="rest",
        method="POST",
        path="/me/sendMail",
        base_url="https://graph.microsoft.com/v1.0",
        source="backend/app/connectors/microsoft365.py (root from _graph_user_root, line 19)",
        note="Outlook actions share the Microsoft Graph mail implementation.",
    ),
    "stripe.invoices.list": ManualApiReference(
        kind="sdk",
        method="GET",
        path="/v1/invoices",
        base_url="https://api.stripe.com",
        source="backend/app/connectors/stripe_api.py:103 (stripe.Invoice.list)",
        note="Issued by the Stripe Python SDK, so no URL literal exists in our code.",
    ),
    "stripe.subscriptions.get": ManualApiReference(
        kind="sdk",
        method="GET",
        path="/v1/subscriptions/{subscription_id}",
        base_url="https://api.stripe.com",
        source="backend/app/connectors/stripe_api.py:120 (stripe.Subscription.retrieve)",
        note="Issued by the Stripe Python SDK.",
    ),
    "stripe.subscriptions.update": ManualApiReference(
        kind="sdk",
        method="POST",
        path="/v1/subscriptions/{subscription_id}",
        base_url="https://api.stripe.com",
        source="backend/app/connectors/stripe_api.py:140 (stripe.Subscription.modify)",
        note="Stripe updates are POST, not PATCH. Issued by the SDK.",
    ),
    # ---- SMTP, not HTTP --------------------------------------------------
    "email.send": ManualApiReference(
        kind="smtp",
        source="backend/app/connectors/email.py:32 (send_email_smtp)",
        note="Sends over SMTP to the connector's configured host. No REST endpoint exists.",
    ),
    "email.send.template": ManualApiReference(
        kind="smtp",
        source="backend/app/services/tool_service.py:2692",
        note="Renders a template then delegates to the same SMTP send path.",
    ),
    "email.batch.send": ManualApiReference(
        kind="smtp",
        source="backend/app/connectors/email.py:32 (send_email_smtp, per recipient)",
        note="Loops the SMTP send. No REST endpoint exists.",
    ),
    "email.messages.queue": ManualApiReference(
        kind="local",
        source="backend/app/services/tool_service.py:2660",
        note="Queues in-process for the SMTP sender; no vendor call at queue time.",
    ),
    "email.delivery.status": ManualApiReference(
        kind="local",
        source="backend/app/services/tool_service.py:2688",
        note="Returns status 'unknown' with a note that delivery status needs "
        "provider webhooks. It makes no outbound call at all.",
    ),
    # ---- customer-configured targets ------------------------------------
    "webhook.post": ManualApiReference(
        kind="caller_supplied",
        method="POST",
        path="{connector.allowed_hosts[0]}{path}",
        source="backend/app/services/tool_service.py:_exec_webhook_post",
        note="Host comes from the connector's allowed_hosts and the path from "
        "call params. There is no fixed vendor endpoint to diff.",
    ),
    "clay.leads.push": ManualApiReference(
        kind="caller_supplied",
        method="POST",
        path="{connector.webhook_url}",
        source="backend/app/connectors/clay_api.py:198 (request_enrichment)",
        note="Posts to the Clay table webhook URL stored in connector config. "
        "Each customer's URL differs, so there is no shared endpoint.",
    ),
    "clay.enrichments.request": ManualApiReference(
        kind="caller_supplied",
        method="POST",
        path="{connector.webhook_url}",
        source="backend/app/connectors/clay_api.py:198 (request_enrichment)",
        note="Same customer-specific Clay webhook URL as clay.leads.push.",
    ),
    "clay.tables.list": ManualApiReference(
        kind="local",
        source="backend/app/services/clay_tools.py:_exec_tables_list",
        note="Returns the tables recorded in connector config. Clay publishes no "
        "list-tables API for webhook-based connections.",
    ),
    "clay.workflows.output.get": ManualApiReference(
        kind="local",
        source="backend/app/services/clay_tools.py:_exec_workflows_output_get",
        note="Reads configured destinations plus records passed from the "
        "upstream step. No Clay API call.",
    ),
    # ---- locally computed, no vendor involved ---------------------------
    "clio.conflict.checklist": ManualApiReference(
        kind="local",
        source="backend/app/services/clio_tools.py:_exec_clio_conflict_checklist",
        note="Builds a static conflict-check checklist in process.",
    ),
    "clio.intake.tasks": ManualApiReference(
        kind="local",
        source="backend/app/services/clio_tools.py:_exec_clio_intake_tasks",
        note="Builds a static intake task list in process.",
    ),
    "fhir.prior_auth.checklist": ManualApiReference(
        kind="local",
        source="backend/app/services/fhir_tools.py:_exec_fhir_prior_auth_checklist",
        note="Static prior-authorisation checklist; no FHIR server call.",
    ),
    "real_estate.handoff.brief": ManualApiReference(
        kind="local",
        source="backend/app/services/real_estate_tools.py:_exec_real_estate_handoff_brief",
        note="Static handoff checklist built from HANDOFF_CHECKLIST.",
    ),
    "real_estate.mls.note": ManualApiReference(
        kind="local",
        source="backend/app/services/real_estate_tools.py:_exec_real_estate_mls_note",
        note="Static MLS note sections built from MLS_NOTE_SECTIONS.",
    ),
    "platform.health.snapshot": ManualApiReference(
        kind="local",
        source="backend/app/services/platform_health_tools.py",
        note="Reads Gravitre's own audit_events / health tables. Internal, not a vendor API.",
    ),
    "ai_visibility_ui.surfaces.list": ManualApiReference(
        kind="local",
        source="backend/app/services/ai_visibility_ui_tools.py:_exec_surfaces_list",
        note="Returns the static list of supported AI surfaces.",
    ),
    "ai_visibility_ui.captures.export": ManualApiReference(
        kind="local",
        source="backend/app/services/ai_visibility_ui_tools.py:_exec_captures_export",
        note="Formats captures already held in memory; no outbound call.",
    ),
    "ai_visibility_ui.mentions.check": ManualApiReference(
        kind="browser_agent",
        source="backend/app/services/ai_visibility_ui_tools.py:_exec_mentions_check",
        note="Drives a browser session against an AI surface. There is no vendor "
        "API contract to diff — the 'endpoint' is a rendered web page.",
    ),
    "ai_visibility_ui.prompts.batch": ManualApiReference(
        kind="browser_agent",
        source="backend/app/services/ai_visibility_ui_tools.py:_exec_prompts_batch",
        note="Batch form of ai_visibility_ui.mentions.check; same browser path.",
    ),
    # ---- catalog entries with no executor -------------------------------
    "webhook.connectors.get": ManualApiReference(
        kind="unregistered",
        source="backend/app/services/tool_service.py:_TOOL_REGISTRY (absent)",
        note="Declared in the catalog but has no executor, so invoke_tool cannot "
        "run it. Reported rather than mapped.",
    ),
    "webhook.post.replay": ManualApiReference(
        kind="unregistered",
        source="backend/app/services/tool_service.py:_TOOL_REGISTRY (absent)",
        note="Declared in the catalog but has no executor, so invoke_tool cannot "
        "run it. Reported rather than mapped.",
    ),
}


def manual_reference(action: str) -> ManualApiReference | None:
    return MANUAL_API_REFERENCES.get(action)
