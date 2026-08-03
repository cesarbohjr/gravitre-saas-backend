"""Browser extension front door onto existing catalog + Module A.

Not a parallel action system: reads/writes go through invoke_tool and
catalog_write_authority; terminals use finalize_execution_outcome.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext

logger = get_logger(__name__)

# Governed catalog actions only (no DOM automation substitutes).
EXTENSION_READ_ACTIONS = frozenset(
    {
        "apollo.people.match",
        "apollo.contacts.search",
        "apollo.people.search",
        "apollo.organizations.search",
        "hubspot.contacts.search",
        "hubspot.companies.search",
        "salesforce.leads.search",
        "slack.users.info",
    }
)
EXTENSION_WRITE_ACTIONS = frozenset(
    {
        "apollo.lists.create",
        "apollo.lists.add",
        "apollo.contacts.create",
        "hubspot.lists.create",
        "hubspot.lists.add_contact",
        "hubspot.contacts.create",
        "salesforce.leads.create",
    }
)
EXTENSION_ALLOWED_ACTIONS = EXTENSION_READ_ACTIONS | EXTENSION_WRITE_ACTIONS

# Explicit host → surface map. company_site / careers_about use activeTab (no fixed host).
SURFACE_HOSTS = {
    "linkedin": ("linkedin.com", "www.linkedin.com"),
    "gmail": ("mail.google.com",),
    "outlook": ("outlook.office.com", "outlook.live.com", "outlook.office365.com"),
    "salesforce": ("lightning.force.com", "salesforce.com", "force.com"),
    "slack": ("app.slack.com",),
    "company_site": (),
}

# Hosts the MV3 extension is allowed to inject on (beyond activeTab). Keep in sync with manifest.
EXTENSION_ALLOWLISTED_HOST_SUFFIXES = (
    "linkedin.com",
    "mail.google.com",
    "outlook.office.com",
    "outlook.live.com",
    "outlook.office365.com",
    "lightning.force.com",
    "salesforce.com",
    "force.com",
    "app.slack.com",
)

_CAREERS_ABOUT_PATH_MARKERS = (
    "/careers",
    "/career",
    "/jobs",
    "/job",
    "/about",
    "/about-us",
    "/company",
    "/team",
)


def detect_surface(page_url: str | None, page_context: dict[str, Any] | None = None) -> str:
    host = ""
    path = ""
    text = str(page_url or "").strip().lower()
    if "://" in text:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(text)
            host = (parsed.hostname or "").lower()
            path = (parsed.path or "").lower()
        except Exception:  # noqa: BLE001
            host = ""
            path = ""
    ctx = page_context or {}
    explicit = str(ctx.get("source") or ctx.get("surface") or "").strip().lower()
    if explicit in {"salesforce", "slack", "linkedin", "gmail", "outlook", "careers_about", "company_site"}:
        if explicit == "company_site" and any(m in path for m in _CAREERS_ABOUT_PATH_MARKERS):
            return "careers_about"
        return explicit
    for surface, hosts in SURFACE_HOSTS.items():
        if surface == "company_site":
            continue
        if any(host == h or host.endswith("." + h) for h in hosts):
            return surface
    if any(m in path for m in _CAREERS_ABOUT_PATH_MARKERS):
        return "careers_about"
    return "company_site"


def host_is_allowlisted(page_url: str | None) -> bool:
    host = ""
    text = str(page_url or "").strip().lower()
    if "://" in text:
        try:
            from urllib.parse import urlparse

            host = (urlparse(text).hostname or "").lower()
        except Exception:  # noqa: BLE001
            host = ""
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in EXTENSION_ALLOWLISTED_HOST_SUFFIXES)


def record_extension_usage_signal(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    page_url: str | None,
    surface: str | None = None,
    invoked: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    """Honest usage signal for prioritization — including non-allowlisted hosts.

    Writes via existing audit path (no parallel analytics system).
    """
    from app.workflows.audit import write_audit_event

    detected = detect_surface(page_url, {"source": surface} if surface else None)
    allowed = host_is_allowlisted(page_url) or detected in {"company_site", "careers_about"}
    payload = {
        "page_url": (page_url or "")[:2000],
        "surface": detected,
        "surface_requested": surface,
        "host_allowlisted": host_is_allowlisted(page_url),
        "active_tab_eligible": detected in {"company_site", "careers_about"},
        "invoked": bool(invoked),
        "note": (note or "")[:500] or None,
        "extension_version": "0.2.0",
    }
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action="extension.usage_signal",
        resource_type="browser_extension",
        resource_id=org_id,
        metadata=payload,
    )
    return {"ok": True, "surface": detected, "allowlisted": allowed, **payload}


def assert_extension_action(action: str) -> str:
    normalized = str(action or "").strip()
    if normalized not in EXTENSION_ALLOWED_ACTIONS:
        raise ValueError(
            f"Action '{normalized}' is not allowed from the browser extension. "
            "Use a governed catalog action from the v1 allowlist, or open Gravitree chat."
        )
    registered = set(list_registered_actions())
    if normalized not in registered:
        raise ValueError(f"Action '{normalized}' is not registered on this stack.")
    return normalized


def _apollo_person_id(match_data: dict[str, Any]) -> str | None:
    person = match_data.get("person") or match_data.get("contact") or match_data
    if not isinstance(person, dict):
        person = match_data
    for key in ("id", "contact_id", "person_id", "primary_contact_id"):
        value = person.get(key) if isinstance(person, dict) else None
        if value is None and isinstance(match_data, dict):
            value = match_data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _hubspot_contact_id(match_data: dict[str, Any]) -> str | None:
    results = match_data.get("results") or match_data.get("contacts") or []
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict) and first.get("id"):
            return str(first["id"]).strip()
    if match_data.get("id"):
        return str(match_data["id"]).strip()
    if match_data.get("contact_id"):
        return str(match_data["contact_id"]).strip()
    return None


def _suggestion(
    *,
    sid: str,
    label: str,
    action: str,
    params: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": sid,
        "label": label,
        "invokeAction": action,
        "kind": "write",
        "requiresApproval": invoke_action_requires_write_approval(action),
        "params": params or {},
    }
    if note:
        payload["note"] = note
    return payload


def connected_integrations(client: Any, org_id: str, environment_name: str = "production") -> list[str]:
    rows = (
        client.table("connectors")
        .select("type, status")
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(100)
        .execute()
    ).data or []
    out: list[str] = []
    for row in rows:
        if str(row.get("status") or "").lower() not in {"active", "connected", "healthy"}:
            continue
        vendor = str(row.get("type") or "").strip().lower()
        if vendor and vendor not in out:
            out.append(vendor)
    return out


def enrich_from_page_context(
    ctx: ToolContext,
    *,
    page_url: str | None,
    page_context: dict[str, Any],
    connected: list[str],
) -> dict[str, Any]:
    """Run catalog reads against page-derived identity fields."""
    surface = detect_surface(page_url, page_context)
    full_name = str(page_context.get("fullName") or page_context.get("name") or "").strip()
    first = str(page_context.get("firstName") or "").strip()
    last = str(page_context.get("lastName") or "").strip()
    if not first and full_name:
        parts = full_name.split(None, 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""
    email = str(page_context.get("email") or "").strip()
    company = str(page_context.get("company") or page_context.get("organization") or "").strip()
    domain = str(page_context.get("domain") or "").strip()
    title = str(page_context.get("title") or page_context.get("headline") or "").strip()

    matches: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []

    if "apollo" in connected and (email or full_name or (first and last)):
        params: dict[str, Any] = {}
        if email:
            params["email"] = email
        if domain:
            params["domain"] = domain
        if first:
            params["first_name"] = first
        if last:
            params["last_name"] = last
        if company:
            params["organization_name"] = company
        if page_context.get("linkedinUrl") or (page_url and "linkedin.com/in/" in page_url.lower()):
            params["linkedin_url"] = str(page_context.get("linkedinUrl") or page_url)
        result = invoke_tool(ctx, "apollo.people.match", params)
        apollo_data = result.data if isinstance(result.data, dict) else {}
        matches.append(
            {
                "action": "apollo.people.match",
                "success": bool(result.success),
                "error": result.error_message,
                "data": apollo_data,
                "confidenceLabel": "matched" if result.success else "unavailable",
            }
        )
        create_params: dict[str, Any] = {
            "first_name": first or "Unknown",
            "last_name": last or "Contact",
        }
        if email:
            create_params["email"] = email
        if company:
            create_params["organization_name"] = company
        suggestions.append(
            _suggestion(
                sid="apollo-contact-create",
                label="Create Apollo contact",
                action="apollo.contacts.create",
                params=create_params,
            )
        )
        person_id = _apollo_person_id(apollo_data) if result.success else None
        if person_id:
            suggestions.append(
                _suggestion(
                    sid="apollo-list-add",
                    label="Add to Apollo list",
                    action="apollo.lists.add",
                    params={
                        "entity_ids": [person_id],
                        "label_names": ["Extension Prospects"],
                        "modality": "contacts",
                    },
                    note="Uses list name 'Extension Prospects' (created if missing).",
                )
            )

    if "hubspot" in connected and (email or full_name):
        # Prefer search; create is offered as a gated suggestion only.
        filter_groups = []
        if email:
            filter_groups = [
                {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
            ]
        elif full_name:
            filter_groups = [
                {
                    "filters": [
                        {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": first or full_name}
                    ]
                }
            ]
        hs_data: dict[str, Any] = {}
        hs_contact_id: str | None = None
        if filter_groups:
            result = invoke_tool(
                ctx,
                "hubspot.contacts.search",
                {"filter_groups": filter_groups, "limit": 5},
            )
            hs_data = result.data if isinstance(result.data, dict) else {}
            hs_contact_id = _hubspot_contact_id(hs_data) if result.success else None
            matches.append(
                {
                    "action": "hubspot.contacts.search",
                    "success": bool(result.success),
                    "error": result.error_message,
                    "data": hs_data,
                    "confidenceLabel": "matched" if result.success and hs_contact_id else "unavailable",
                }
            )
        hs_create: dict[str, Any] = {
            "properties": {
                k: v
                for k, v in {
                    "email": email or None,
                    "firstname": first or None,
                    "lastname": last or "Contact",
                    "company": company or None,
                    "jobtitle": title or None,
                }.items()
                if v
            }
        }
        suggestions.append(
            _suggestion(
                sid="hubspot-contact-create",
                label="Create HubSpot contact",
                action="hubspot.contacts.create",
                params=hs_create,
            )
        )
        if hs_contact_id:
            suggestions.append(
                _suggestion(
                    sid="hubspot-list-add",
                    label="Add to HubSpot list",
                    action="hubspot.lists.add_contact",
                    params={"list_id": "", "contact_id": hs_contact_id},
                    note="Enter a HubSpot list id before approving.",
                )
            )
        else:
            suggestions.append(
                _suggestion(
                    sid="hubspot-list-create",
                    label="Create HubSpot list",
                    action="hubspot.lists.create",
                    params={
                        "name": (
                            f"{company} — Extension"
                            if company
                            else f"Extension list {full_name or 'contacts'}"
                        )[:100],
                    },
                )
            )

    if "apollo" in connected and (company or domain) and surface in {
        "company_site",
        "careers_about",
        "linkedin",
        "salesforce",
    }:
        org_params: dict[str, Any] = {"per_page": 5}
        if company:
            org_params["q_organization_name"] = company
        if domain:
            org_params["q_organization_domains_list"] = [domain]
        result = invoke_tool(ctx, "apollo.organizations.search", org_params)
        matches.append(
            {
                "action": "apollo.organizations.search",
                "success": bool(result.success),
                "error": result.error_message,
                "data": result.data if isinstance(result.data, dict) else {},
                "confidenceLabel": "estimate" if result.success else "unavailable",
            }
        )

    # Salesforce web — catalog reads/writes only (no Lightning DOM automation).
    if "salesforce" in connected and (email or company or full_name):
        sf_params: dict[str, Any] = {"limit": 5}
        if email:
            sf_params["email"] = email
        if company:
            sf_params["company"] = company
        result = invoke_tool(ctx, "salesforce.leads.search", sf_params)
        matches.append(
            {
                "action": "salesforce.leads.search",
                "success": bool(result.success),
                "error": result.error_message,
                "data": result.data if isinstance(result.data, dict) else {},
                "confidenceLabel": "matched" if result.success else "unavailable",
            }
        )
        fields: dict[str, Any] = {
            "LastName": last or full_name or "Unknown",
            "Company": company or "Unknown",
        }
        if first:
            fields["FirstName"] = first
        if email:
            fields["Email"] = email
        if title:
            fields["Title"] = title
        suggestions.append(
            _suggestion(
                sid="salesforce-lead-create",
                label="Create Salesforce lead",
                action="salesforce.leads.create",
                params={"fields": fields},
                note="Uses salesforce.leads.create — not Salesforce UI clicking.",
            )
        )

    # Slack web — page context only; identity via catalog (Apollo/HubSpot above).
    if surface == "slack" and "slack" in connected:
        slack_user = str(page_context.get("slackUserId") or "").strip()
        if slack_user:
            result = invoke_tool(ctx, "slack.users.info", {"user": slack_user})
            matches.append(
                {
                    "action": "slack.users.info",
                    "success": bool(result.success),
                    "error": result.error_message,
                    "data": result.data if isinstance(result.data, dict) else {},
                    "confidenceLabel": "matched" if result.success else "unavailable",
                }
            )

    open_in_app = "/ai"
    if full_name or company:
        q = full_name or company
        open_in_app = f"/ai?q={q}"

    voice = "Enrichment from connected Gravitree connectors — approve before any write."
    if surface == "careers_about":
        voice = "Careers/about page — firmographic enrich via catalog, not job-board scraping."
    elif surface == "salesforce":
        voice = "Salesforce overlay uses governed catalog actions only — no Lightning automation."
    elif surface == "slack":
        voice = "Slack overlay extracts page context; writes go through Apollo/HubSpot/Salesforce catalog."

    return {
        "surface": surface,
        "pageUrl": page_url,
        "extracted": {
            "fullName": full_name or None,
            "firstName": first or None,
            "lastName": last or None,
            "email": email or None,
            "company": company or None,
            "domain": domain or None,
            "title": title or None,
        },
        "matches": matches,
        "suggestions": suggestions,
        "openInGravitreeUrl": open_in_app,
        "connectedIntegrations": connected,
        "voiceNote": voice,
    }


EXTENSION_APPROVAL_TYPE = "extension_write"
EXTENSION_GATE_TYPE = "browser_extension_write"


def _stage_extension_write_confirmation(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    action: str,
    params: dict[str, Any],
    page_url: str | None,
) -> dict[str, Any]:
    """Persist awaiting_confirm like chat pending_task — server-issued token only."""
    import secrets

    from app.services.approval_record_service import create_contract_approval

    confirmation_token = secrets.token_urlsafe(32)
    needs_approval = invoke_action_requires_write_approval(action)
    pending = {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "gate_type": EXTENSION_GATE_TYPE,
        "confirmation_token": confirmation_token,
        "invoke_action": action,
        "args": dict(params or {}),
        "page_url": page_url,
        "requires_approval": needs_approval,
        "source": "browser_extension",
    }
    row = create_contract_approval(
        client,
        org_id=org_id,
        title=f"Approve extension write: {action}",
        description=(
            f"Browser extension proposed {action}. "
            "Confirm with the server-issued token to execute — same gate as chat awaiting_confirm."
        ),
        approval_type=EXTENSION_APPROVAL_TYPE,
        priority="medium",
        status="pending",
        requested_by=user_id,
        context=pending,
    )
    if not row or not row.get("id"):
        raise ValueError(
            "Could not stage write confirmation. Retry from the overlay, or open Gravitree chat."
        )
    return {
        "status": "needs_confirmation",
        "invokeAction": action,
        "requiresApproval": needs_approval,
        "params": dict(params or {}),
        "confirmationToken": confirmation_token,
        "approvalId": str(row["id"]),
        "message": (
            "Confirm this governed write. Execution requires the server-issued "
            "confirmationToken from this awaiting_confirm step — client confirmed flags are ignored."
        ),
        "pageUrl": page_url,
    }


def _load_extension_pending_confirm(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    confirmation_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate a durable awaiting_confirm row for this user/org."""
    token = str(confirmation_token or "").strip()
    if not token:
        raise ValueError("confirmationToken is required to execute a write from the extension.")

    rows = (
        client.table("approvals")
        .select("id, org_id, status, requested_by, type, context")
        .eq("org_id", org_id)
        .eq("type", EXTENSION_APPROVAL_TYPE)
        .eq("status", "pending")
        .eq("requested_by", user_id)
        .contains("context", {"confirmation_token": token, "status": "awaiting_confirm"})
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        raise ValueError(
            "No awaiting_confirm write found for this confirmationToken. "
            "Propose the action again from the overlay, then approve."
        )
    row = dict(rows[0])
    context = row.get("context") if isinstance(row.get("context"), dict) else {}
    if str(context.get("gate_type") or "") != EXTENSION_GATE_TYPE:
        raise ValueError("Confirmation token is not valid for browser extension writes.")
    if str(context.get("status") or "") != "awaiting_confirm":
        raise ValueError("This write confirmation is no longer awaiting confirm.")
    action = assert_extension_action(str(context.get("invoke_action") or ""))
    args = context.get("args") if isinstance(context.get("args"), dict) else {}
    return row, {
        "invoke_action": action,
        "args": dict(args),
        "page_url": context.get("page_url"),
        "approval_id": str(row["id"]),
    }


def _consume_extension_pending_confirm(
    client: Any,
    *,
    org_id: str,
    approval_id: str,
    user_id: str,
    prior_context: dict[str, Any],
) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    merged = dict(prior_context or {})
    merged["status"] = "confirmed"
    merged["confirmed_at"] = now
    # One-time token — drop after consume so replay cannot match awaiting_confirm.
    merged.pop("confirmation_token", None)
    updated = (
        client.table("approvals")
        .update(
            {
                "status": "approved",
                "reviewed_by": user_id,
                "reviewed_at": now,
                "context": merged,
            }
        )
        .eq("id", approval_id)
        .eq("org_id", org_id)
        .eq("status", "pending")
        .eq("requested_by", user_id)
        .execute()
    )
    if not (updated.data or []):
        raise ValueError("Write confirmation was already used or is no longer pending.")


def _alert_extension_finalize_failure(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    run_id: str | None,
    action: str,
    exc: Exception,
) -> None:
    """Same discipline as MODULE_A_FINALIZE_FAILED_FALLBACK_STATUS_STAMP — not log-only."""
    logger.error(
        "MODULE_A_FINALIZE_FAILED_FALLBACK_STATUS_STAMP — investigate "
        "extension finalize_execution_outcome failure action=%s run_id=%s exc=%s",
        action,
        run_id,
        exc,
    )
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            client,
            org_id,
            user_id or "00000000-0000-0000-0000-000000000000",
            "module_a.finalize.fallback",
            "workflow_run",
            run_id or "extension-no-run",
            {
                "severity": "MODULE_A_FINALIZE_FAILED_FALLBACK_STATUS_STAMP",
                "error": str(exc)[:500],
                "path": "browser_extension.execute_extension_action",
                "invoke_action": action,
            },
        )
    except Exception as audit_exc:  # noqa: BLE001
        logger.error(
            "extension finalize fallback audit failed action=%s error=%s",
            action,
            audit_exc,
        )
    if run_id:
        try:
            from app.workflows.repository import update_run

            update_run(
                client,
                run_id,
                status="failed",
                error_message=f"Module A finalize failed: {str(exc)[:500]}",
            )
        except Exception as stamp_exc:  # noqa: BLE001
            logger.error(
                "extension finalize fallback status stamp failed run_id=%s error=%s",
                run_id,
                stamp_exc,
            )


def _run_confirmed_extension_action(
    ctx: ToolContext,
    *,
    org_id: str,
    user_id: str,
    action: str,
    params: dict[str, Any],
    page_url: str | None,
    approval_id: str | None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.services.connector_outcome_effects import (
        classify_write_effect,
        coerce_terminal_status_for_effect,
        is_already_existed_effect,
    )
    from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome
    from app.workflows.repository import create_run, create_step, update_step

    result = invoke_tool(ctx, action, params)
    data = result.data if isinstance(result.data, dict) else {}
    already_existed = is_already_existed_effect(data)
    outcome_effect = classify_write_effect(
        invoke_action=action,
        result_data=data,
        success=bool(result.success),
        metadata={"already_existed": already_existed} if already_existed else None,
    )
    if result.success and already_existed:
        status = "partial_success"
    elif result.success:
        status = "completed"
    else:
        status = "failed"
    status = coerce_terminal_status_for_effect(
        status=status,
        effect=outcome_effect,
        invoke_action=action,
    )

    run_id: str | None = None
    try:
        created = create_run(
            ctx.client,
            org_id=org_id,
            triggered_by=user_id,
            definition_snapshot={
                "name": f"Extension: {action}",
                "source": "browser_extension",
                "steps": [
                    {
                        "id": "extension_action",
                        "name": action,
                        "type": "invoke_tool",
                        "config": {"action": action},
                    }
                ],
            },
            parameters={
                "source": "browser_extension",
                "invoke_action": action,
                "page_url": page_url,
                "action_args": params,
                "outcome_effect": outcome_effect,
                "already_existed": already_existed,
                "approval_id": approval_id,
            },
            run_hash=f"ext-{uuid4().hex[:16]}",
            workflow_id=None,
            environment_name=ctx.environment_name or "production",
            trigger_type="api",
            run_type="execute",
        )
        run_id = str(created["id"])
        step = create_step(
            ctx.client,
            run_id,
            org_id,
            step_id="extension_action",
            step_index=0,
            step_name=action,
            step_type="invoke_tool",
        )
        now = datetime.now(timezone.utc).isoformat()
        update_step(
            ctx.client,
            str(step["id"]),
            status="completed" if result.success else "failed",
            output_snapshot={
                "summary": (result.error_message or str(data.get("message") or action))[:2000],
                "invoke_action": action,
                "success": bool(result.success),
                "outcome_effect": outcome_effect,
                "already_existed": already_existed,
                "result_url": data.get("result_url"),
                "external_url": data.get("external_url") or data.get("result_url"),
                "structured": data,
            },
            started_at=now,
            completed_at=now,
            error_message=None if result.success else (result.error_message or "Action failed"),
        )
        finalize_execution_outcome(
            ctx.client,
            org_id=org_id,
            status=status,
            source="browser_extension",
            actor_id=user_id,
            run_id=run_id,
            persist_run=True,
            error_summary=None if result.success else (result.error_message or "Action failed"),
            verified_output=VerifiedOutputRef(
                summary=(result.error_message or f"{action} via browser extension")[:2000],
                result_url=f"/runs/{run_id}",
                external_url=str(data.get("external_url") or data.get("result_url") or "") or None,
                # notifications.entity_id is uuid — use run_id via as_entity_ref fallback.
                # Vendor list/contact ids stay in metadata / external_entity_id.
                entity_type="workflow_run",
                entity_id=run_id,
                integration=action.split(".", 1)[0],
            ),
            metadata={
                "path": "browser_extension",
                "invoke_action": action,
                "page_url": page_url,
                "outcome_effect": outcome_effect,
                "already_existed": already_existed,
                "action_args": params,
                "approval_id": approval_id,
                "vendor_entity_id": str(
                    data.get("entity_id") or data.get("contact_id") or data.get("list_id") or ""
                )
                or None,
                "connector_output_refs": [
                    {
                        "label": action,
                        "invoke_action": action,
                        "integration": action.split(".", 1)[0],
                        "external_url": data.get("external_url") or data.get("result_url"),
                        "entity_id": data.get("entity_id") or data.get("contact_id") or data.get("list_id"),
                        "outcome_effect": outcome_effect,
                        "success": bool(result.success),
                    }
                ],
            },
        )
    except Exception as exc:  # noqa: BLE001
        _alert_extension_finalize_failure(
            ctx.client,
            org_id=org_id,
            user_id=user_id,
            run_id=run_id,
            action=action,
            exc=exc,
        )

    return {
        "status": status,
        "invokeAction": action,
        "success": bool(result.success),
        "error": result.error_message,
        "runId": run_id,
        "outcomeUrl": f"/runs/{run_id}" if run_id else None,
        "businessOutcomeUrl": f"/outcomes/{run_id}" if run_id else None,
        "data": data,
        "outcomeEffect": outcome_effect,
        "approvalId": approval_id,
        "source": "browser_extension",
    }


def execute_extension_action(
    ctx: ToolContext,
    *,
    org_id: str,
    user_id: str,
    action: str | None,
    params: dict[str, Any],
    page_url: str | None,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    """Stage writes into durable awaiting_confirm; execute only with server-issued token.

    Client ``confirmed`` flags are never trusted. Confirm turn loads args from the
    staged approval row (chat pending_task equivalent), not from client-supplied params.
    """
    token = str(confirmation_token or "").strip()
    if token:
        row, pending = _load_extension_pending_confirm(
            ctx.client,
            org_id=org_id,
            user_id=user_id,
            confirmation_token=token,
        )
        prior_context = row.get("context") if isinstance(row.get("context"), dict) else {}
        _consume_extension_pending_confirm(
            ctx.client,
            org_id=org_id,
            approval_id=str(row["id"]),
            user_id=user_id,
            prior_context=prior_context,
        )
        return _run_confirmed_extension_action(
            ctx,
            org_id=org_id,
            user_id=user_id,
            action=str(pending["invoke_action"]),
            params=dict(pending["args"] or {}),
            page_url=pending.get("page_url") or page_url,
            approval_id=str(pending["approval_id"]),
        )

    if not action:
        raise ValueError("invokeAction is required when confirmationToken is not provided.")
    action = assert_extension_action(action)
    if action in EXTENSION_WRITE_ACTIONS:
        # Always stage — never execute a write on the propose turn.
        return _stage_extension_write_confirmation(
            ctx.client,
            org_id=org_id,
            user_id=user_id,
            action=action,
            params=params,
            page_url=page_url,
        )

    # Reads only (rare via this endpoint — enrich is the normal read path).
    return _run_confirmed_extension_action(
        ctx,
        org_id=org_id,
        user_id=user_id,
        action=action,
        params=params,
        page_url=page_url,
        approval_id=None,
    )
