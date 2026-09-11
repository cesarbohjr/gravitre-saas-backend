"""Isolated-org-only triggers for live Response Composer failure-mode proof.

These are not customer-facing tools. They exist so a real Postgres
``statement_timeout`` and a real connector OAuth HTTP 403 can be induced
on the same chat path a customer uses, instead of hoping the model happens
to hit those faults.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.conversation_write_guard import is_isolated_conversation_test_org
from app.services.tool_service import _classify_error, _handle_hubspot_error, _vendor_api_error
from app.services.tool_types import NormalizedResult, ToolError
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

COMPOSER_FAILURE_PROBE_HEADER = "X-Gravitre-Composer-Failure-Probe"
PROBE_STATEMENT_TIMEOUT = "statement_timeout"
PROBE_OAUTH_PERMISSION = "oauth_permission_denied"
ALLOWED_PROBES = frozenset({PROBE_STATEMENT_TIMEOUT, PROBE_OAUTH_PERMISSION})
AUDIT_ACTION = "composer.failure_probe.completed"

# HubSpot Conversations inbox list typically 403s a CRM-only OAuth token.
_HUBSPOT_SCOPE_PATH = "/conversations/v3/conversations/inboxes"
# A customer id the isolated org's Google Ads token will not own.
_ADS_FOREIGN_CUSTOMER_ID = "1111111111"


def resolve_composer_failure_probe(*, org_id: str | None, header_value: str | None) -> str | None:
    if not is_isolated_conversation_test_org(org_id):
        return None
    token = str(header_value or "").strip().lower()
    if token in ALLOWED_PROBES:
        return token
    return None


# The probes above are tool-level faults the Composer already handles. This one
# is different: it forces the *whole* cognitive turn to raise, which is the only
# way to exercise the voice path's except-handler -- the site that used to push
# str(exc) into an ErrorFrame for the user to hear.
#
# A voice turn cannot carry a probe header, because the transport is a WebSocket
# whose only per-session identifiers are org and conversation. So this one is
# keyed on a sentinel conversation id, behind the same isolated-org gate as the
# HTTP probes, meaning a real org cannot reach it however it is called.
VOICE_TURN_FAILURE_CONVERSATION_ID = "f07e57c0-0000-4000-8000-c04e57a0fa11"

# Deliberately shaped like the leak it guards against: carries a kernel name and
# a backend path, so if this text ever reaches a user the Composer's own
# looks_like_raw_backend detector is guaranteed to flag it. A bland message could
# pass a leak scan while still proving nothing.
VOICE_TURN_FAILURE_MESSAGE = (
    "CognitiveTurnKernel probe fault: statement timeout raised in backend/app"
)


def is_voice_turn_failure_probe(*, org_id: str | None, conversation_id: str | None) -> bool:
    if not is_isolated_conversation_test_org(org_id):
        return False
    return (
        str(conversation_id or "").strip().lower() == VOICE_TURN_FAILURE_CONVERSATION_ID
    )


def _postgres_dsn(settings: Any) -> str:
    for raw in (
        getattr(settings, "database_url", None),
        os.environ.get("DATABASE_URL"),
        os.environ.get("SUPABASE_DB_URL"),
        os.environ.get("DATABASE_DIRECT_URL"),
    ):
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def _result_from_tool_error(
    exc: Exception, *, action: str, connector_id: str | None = None
) -> NormalizedResult:
    tool_exc = exc if isinstance(exc, ToolError) else _classify_error(exc)
    return NormalizedResult(
        success=False,
        action=action,
        error_code=tool_exc.code,
        error_message=str(tool_exc),
        connector_id=connector_id,
    )


async def induce_statement_timeout(
    settings: Any, *, client: Any | None = None
) -> tuple[NormalizedResult, dict[str, Any]]:
    """Cancel a real Postgres statement. Returns (envelope, evidence)."""
    evidence: dict[str, Any] = {"probe": PROBE_STATEMENT_TIMEOUT}
    dsn = _postgres_dsn(settings)
    last_exc: Exception | None = None
    if dsn:
        try:
            import asyncpg  # type: ignore

            conn = await asyncpg.connect(dsn, timeout=10)
            try:
                await conn.execute("SET statement_timeout = '120ms'")
                await conn.fetchval("SELECT pg_sleep(3)")
            finally:
                await conn.close()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            evidence["driver"] = "asyncpg"
            evidence["exception_class"] = type(exc).__name__
            evidence["sqlstate"] = str(
                getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None) or ""
            )
            classified = _classify_error(exc)
            evidence["classified_code"] = classified.code
            if classified.code == "statement_timeout":
                return _result_from_tool_error(exc, action="postgres.query"), evidence
    if client is not None:
        try:
            client.rpc("gravitre_probe_statement_timeout").execute()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            evidence["driver"] = evidence.get("driver") or "supabase_rpc"
            evidence["exception_class"] = type(exc).__name__
            classified = _classify_error(exc)
            evidence["classified_code"] = classified.code
            if classified.code == "statement_timeout":
                if "57014" in str(exc) and not evidence.get("sqlstate"):
                    evidence["sqlstate"] = "57014"
                return _result_from_tool_error(exc, action="postgres.query"), evidence
            msg = str(exc).lower()
            if "statement timeout" in msg or "57014" in msg:
                evidence["sqlstate"] = evidence.get("sqlstate") or "57014"
                return (
                    NormalizedResult(
                        success=False,
                        action="postgres.query",
                        error_code="statement_timeout",
                        error_message=str(exc)[:400],
                    ),
                    evidence,
                )
    if last_exc is not None:
        return _result_from_tool_error(last_exc, action="postgres.query"), evidence
    return (
        NormalizedResult(
            success=False,
            action="postgres.query",
            error_code="tool_error",
            error_message="statement_timeout probe could not reach Postgres",
        ),
        {**evidence, "classified_code": "tool_error"},
    )


def _hubspot_conversations_403(access_token: str) -> tuple[int, str]:
    response = httpx.get(
        f"https://api.hubapi.com{_HUBSPOT_SCOPE_PATH}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20.0,
    )
    return response.status_code, (response.text or "")[:400]


def induce_oauth_permission_denied(
    *,
    client: Any,
    org_id: str,
    settings: Any,
    environment_name: str = "production",
) -> tuple[NormalizedResult, dict[str, Any]]:
    """Call a connected OAuth vendor with the real token in a way that 403s."""
    from app.connectors.repository import get_connector_by_type

    evidence: dict[str, Any] = {"probe": PROBE_OAUTH_PERMISSION}
    hubspot = get_connector_by_type(client, org_id, "hubspot", environment_name=environment_name)
    if hubspot:
        from app.connectors.hubspot import HubSpotAPIError
        from app.connectors.hubspot_oauth import ensure_hubspot_access_token

        cid = str(hubspot["id"])
        token, err = ensure_hubspot_access_token(
            client,
            org_id,
            cid,
            settings,
            environment_name=environment_name,
            validate_remote=False,
        )
        if token:
            status, body = _hubspot_conversations_403(token)
            evidence.update(
                {
                    "vendor": "hubspot",
                    "connector_id": cid,
                    "vendor_http_status": status,
                    "vendor_path": _HUBSPOT_SCOPE_PATH,
                }
            )
            if status == 403:
                hs_exc = HubSpotAPIError(
                    f"HubSpot API 403: {_HUBSPOT_SCOPE_PATH}",
                    status_code=403,
                    details=body,
                )
                classified = _handle_hubspot_error(hs_exc)
                evidence["classified_code"] = classified.code
                return (
                    _result_from_tool_error(
                        classified,
                        action="hubspot.conversations.inboxes.list",
                        connector_id=cid,
                    ),
                    evidence,
                )
            evidence["hubspot_status_not_403"] = status
        else:
            evidence["hubspot_token_error"] = err

    ads = get_connector_by_type(client, org_id, "google_ads", environment_name=environment_name)
    if ads:
        from app.connectors.google_ads import GoogleAdsAPIError, list_campaigns
        from app.connectors.google_vendor_oauth import ensure_google_vendor_session

        cid = str(ads["id"])
        token, oauth_err = ensure_google_vendor_session(
            client, org_id, cid, settings, environment_name=environment_name
        )
        dev_token = str(getattr(settings, "google_ads_developer_token", "") or "").strip()
        if token and dev_token:
            try:
                list_campaigns(
                    token,
                    _ADS_FOREIGN_CUSTOMER_ID,
                    developer_token=dev_token,
                    limit=1,
                )
                evidence.update(
                    {
                        "vendor": "google_ads",
                        "connector_id": cid,
                        "vendor_http_status": 200,
                        "note": "foreign customer_id unexpectedly succeeded",
                    }
                )
            except GoogleAdsAPIError as exc:
                classified = _vendor_api_error(exc, "google_ads")
                evidence.update(
                    {
                        "vendor": "google_ads",
                        "connector_id": cid,
                        "vendor_http_status": getattr(exc, "status_code", None),
                        "classified_code": classified.code,
                        "customer_id": _ADS_FOREIGN_CUSTOMER_ID,
                    }
                )
                if classified.code == "permission_denied" or getattr(exc, "status_code", None) == 403:
                    return (
                        _result_from_tool_error(
                            classified,
                            action="googleads.campaigns.list",
                            connector_id=cid,
                        ),
                        evidence,
                    )
        else:
            evidence["google_ads_token_error"] = oauth_err or "missing developer token"

    return (
        NormalizedResult(
            success=False,
            action="oauth.permission_probe",
            error_code="tool_error",
            error_message="oauth permission_denied probe did not receive a vendor HTTP 403",
        ),
        {**evidence, "classified_code": "tool_error"},
    )


async def run_composer_failure_probe(
    probe: str,
    *,
    settings: Any,
    client: Any,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    environment_name: str = "production",
) -> tuple[NormalizedResult, dict[str, Any]]:
    if probe == PROBE_STATEMENT_TIMEOUT:
        result, evidence = await induce_statement_timeout(settings, client=client)
    elif probe == PROBE_OAUTH_PERMISSION:
        result, evidence = induce_oauth_permission_denied(
            client=client,
            org_id=org_id,
            settings=settings,
            environment_name=environment_name,
        )
    else:
        result = NormalizedResult(
            success=False,
            action="composer.failure_probe",
            error_code="validation_error",
            error_message=f"unknown probe {probe}",
        )
        evidence = {"probe": probe, "classified_code": "validation_error"}
    try:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=str(user_id or org_id),
            action=AUDIT_ACTION,
            resource_type="conversation" if conversation_id else "response_composer",
            resource_id=str(conversation_id or org_id),
            metadata={
                "probe": probe,
                "errorCode": result.error_code,
                "action": result.action,
                "vendorHttpStatus": evidence.get("vendor_http_status"),
                "vendor": evidence.get("vendor"),
                "sqlstate": evidence.get("sqlstate"),
                "exceptionClass": evidence.get("exception_class"),
                "classifiedCode": evidence.get("classified_code") or result.error_code,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("composer_failure_probe_audit_skipped error=%s", exc)
    return result, evidence
