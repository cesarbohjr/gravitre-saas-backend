"""Predictive workflow failure detection — heuristic alerts before steps fail (STA-122)."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.connection_health import resolve_connector_auth_status
from app.connectors.constants import ACTIVE_CONNECTOR_STATUSES, connector_environment_candidates
from app.connectors.hubspot_oauth import OAUTH_TOKEN_KEY, load_oauth_tokens, token_needs_refresh
from app.connectors.repository import get_decrypted_secret
from app.intelligence_packs.shared.auth_mode import (
    AuthMode,
    get_auth_mode,
    is_knowledge_base_source,
    requires_tenant_connector,
)
from app.services.agent_tool_permissions import (
    list_agent_tool_permissions,
    required_scopes_for_action,
)
from app.services.tool_service import STEP_TYPE_TO_ACTION
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_active_workflow_version, get_workflow_def, list_workflows
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

# Platform workflow steps — not OAuth connectors; must not trigger "Missing X connector" alerts.
PLATFORM_STEP_TYPES = frozenset(
    {
        "agent",
        "agent_task",
        "rag_query",
        "delay",
        "condition",
        "council",
        "decision",
        "approval",
        "noop",
        "invoke_tool",
        "slack_post_message",
        "email_send",
        "webhook_post",
    }
)

AUDIT_FAILURE_PREDICTION_SCANNED = "workflow.failure_prediction.scanned"
RESOURCE_TYPE_WORKFLOW_FAILURE_ALERT = "workflow_failure_alert"

ALERT_TYPES = (
    "auth_expiry",
    "auth_disconnected",
    "rate_limit_trend",
    "missing_scope",
    "step_failure_risk",
    "connector_missing",
)

SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 4}

AUTH_EXPIRY_CRITICAL_HOURS = 24
AUTH_EXPIRY_HIGH_HOURS = 72
STEP_FAILURE_HIGH_RATE = 0.4
STEP_FAILURE_MEDIUM_RATE = 0.25
MIN_RUNS_FOR_STEP_FAILURE = 5


class FailurePredictionError(Exception):
    code = "FAILURE_PREDICTION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _severity_to_confidence(severity: str) -> float:
    return {
        "low": 0.6,
        "medium": 0.72,
        "high": 0.85,
        "critical": 0.92,
    }.get(severity, 0.65)


def _alert_row(
    *,
    org_id: str,
    workflow_id: str,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    evidence: dict[str, Any],
    step_id: str | None = None,
    connector_id: str | None = None,
) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "step_id": step_id,
        "connector_id": connector_id,
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "message": message,
        "evidence": evidence,
        "confidence": _severity_to_confidence(severity),
        "status": "open",
        "predicted_at": _now_iso(),
    }


def extract_step_requirements(definition: dict[str, Any]) -> list[dict[str, Any]]:
    """Return connector/agent requirements per workflow step."""
    requirements: list[dict[str, Any]] = []
    for step in definition.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or "")
        step_name = str(step.get("name") or step_id)
        step_type = str(step.get("type") or "")
        config = safe_normalize_stored_dict(step, key='config')
        metadata = safe_normalize_stored_dict(step, key='metadata')
        if isinstance(config.get("metadata"), dict):
            metadata = {**metadata, **config["metadata"]}
        action = str(config.get("action") or STEP_TYPE_TO_ACTION.get(step_type) or "").strip()
        if step_type in PLATFORM_STEP_TYPES and not action:
            continue
        connector_type = None
        if action and "." in action:
            connector_type = action.split(".", 1)[0]
        elif step_type and step_type not in PLATFORM_STEP_TYPES:
            connector_type = step_type.split("_", 1)[0]
        if connector_type in {"noop", "platform", "internal"}:
            continue
        connector_id = config.get("connector_id") or config.get("connectorId")
        agent_id = metadata.get("agent_id") or metadata.get("agentId") or config.get("agent_id")
        if not action and not connector_type and not agent_id:
            continue
        requirements.append(
            {
                "stepId": step_id,
                "stepName": step_name,
                "stepType": step_type,
                "action": action or None,
                "connectorType": connector_type,
                "connectorId": str(connector_id) if connector_id else None,
                "agentId": str(agent_id) if agent_id else None,
            }
        )
    return requirements


def _find_active_connector_id(
    client: Any,
    org_id: str,
    connector_type: str,
    *,
    environment_name: str,
) -> str | None:
    from app.intelligence_packs.shared.auth_mode import connector_type_lookup_keys

    statuses = list(ACTIVE_CONNECTOR_STATUSES)
    type_keys = connector_type_lookup_keys(connector_type)
    for type_key in type_keys:
        for env in connector_environment_candidates(environment_name):
            result = (
                client.table("connectors")
                .select("id")
                .eq("org_id", org_id)
                .eq("type", type_key)
                .in_("status", statuses)
                .eq("environment", env)
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
            )
            if result.data:
                return str(result.data[0]["id"])
        result = (
            client.table("connectors")
            .select("id")
            .eq("org_id", org_id)
            .eq("type", type_key)
            .in_("status", statuses)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])
    return None


def _get_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any] | None:
    result = (
        client.table("connectors")
        .select("id,type,vendor,status,environment")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def _load_token_expiry_hours(
    client: Any,
    settings: Settings,
    connector_id: str,
) -> float | None:
    tokens = load_oauth_tokens(client, connector_id, settings)
    if tokens and tokens.get("expires_at"):
        try:
            expires_at = float(tokens["expires_at"])
            return (expires_at - time.time()) / 3600.0
        except (TypeError, ValueError):
            pass
    if not settings.connector_secrets_encryption_key:
        return None
    raw = get_decrypted_secret(client, connector_id, OAUTH_TOKEN_KEY, settings)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    expires_at = payload.get("expires_at")
    if not expires_at:
        return None
    try:
        return (float(expires_at) - time.time()) / 3600.0
    except (TypeError, ValueError):
        return None


def _scope_satisfied(granted: list[str], required: list[str]) -> bool:
    granted_set = {s.strip() for s in granted if s and str(s).strip()}
    if "*" in granted_set:
        return True
    for req in required:
        if req in granted_set:
            return True
        if ":" in req:
            family = req.split(":", 1)[0] + ":*"
            if family in granted_set:
                return True
    return False


def _permission_is_active(row: dict[str, Any]) -> bool:
    expires = row.get("expires_at")
    if not expires:
        return True
    if isinstance(expires, str):
        expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    else:
        expires_at = expires
    return expires_at > _now()


def _agent_has_scope(
    client: Any,
    org_id: str,
    agent_id: str,
    action: str,
    connector_id: str | None,
    connector_type: str | None,
) -> bool:
    required = required_scopes_for_action(action)
    ctype = connector_type or (action.split(".", 1)[0] if "." in action else action)
    rows = [row for row in list_agent_tool_permissions(client, org_id, agent_id) if _permission_is_active(row)]
    if not rows:
        return False
    matching: list[dict[str, Any]] = []
    for row in rows:
        row_connector = row.get("connector_id")
        row_type = (row.get("connector_type") or "").strip()
        if connector_id and row_connector and str(row_connector) == str(connector_id):
            matching.append(row)
        elif connector_id and row_connector:
            continue
        elif row_type and row_type == ctype:
            matching.append(row)
        elif not row_connector and not row_type:
            matching.append(row)
    if not matching:
        return False
    for row in matching:
        scopes = row.get("scopes") or []
        if isinstance(scopes, list) and _scope_satisfied([str(s) for s in scopes], required):
            return True
    return False


def _is_rate_limit_error(error_message: str | None, error_code: str | None) -> bool:
    blob = f"{error_message or ''} {error_code or ''}".lower()
    return "rate limit" in blob or "429" in blob or (error_code or "").lower() in {"rate_limited", "rate_limit"}


def _recent_run_steps(
    client: Any,
    org_id: str,
    workflow_id: str,
    *,
    limit_runs: int = 25,
) -> list[dict[str, Any]]:
    runs_result = (
        client.table("workflow_runs")
        .select("id,created_at")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .order("created_at", desc=True)
        .limit(limit_runs)
        .execute()
    )
    run_rows = list(runs_result.data or [])
    if not run_rows:
        return []
    run_ids = [str(row["id"]) for row in run_rows]
    steps_result = (
        client.table("workflow_steps")
        .select("run_id,step_id,step_name,status,error_code,error_message,completed_at,created_at")
        .eq("org_id", org_id)
        .in_("run_id", run_ids)
        .execute()
    )
    run_created = {str(row["id"]): row.get("created_at") for row in run_rows}
    steps: list[dict[str, Any]] = []
    for row in steps_result.data or []:
        item = dict(row)
        item["run_created_at"] = run_created.get(str(row.get("run_id")))
        steps.append(item)
    return steps


def _resolve_workflow_definition(
    client: Any,
    org_id: str,
    workflow_id: str,
    *,
    environment_name: str,
) -> dict[str, Any]:
    active = get_active_workflow_version(client, org_id, workflow_id, environment_name)
    definition = safe_normalize_stored_dict(active, key="definition") if active else {}
    if definition:
        return definition
    workflow = get_workflow_def(client, org_id, workflow_id)
    if not workflow:
        raise FailurePredictionError("Workflow not found", code="WORKFLOW_NOT_FOUND")
    definition = workflow.get("definition")
    if not isinstance(definition, dict):
        raise FailurePredictionError("Workflow definition missing", code="WORKFLOW_DEFINITION_MISSING")
    return definition


def _compute_risk_score(alerts: list[dict[str, Any]]) -> int:
    if not alerts:
        return 0
    weights = [SEVERITY_WEIGHT.get(str(alert.get("severity") or "low"), 1) for alert in alerts]
    return min(100, int(sum(weights) / len(weights) * 25))


def _serialize_alert(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "orgId": row.get("org_id"),
        "workflowId": row.get("workflow_id"),
        "stepId": row.get("step_id"),
        "connectorId": row.get("connector_id"),
        "alertType": row.get("alert_type"),
        "severity": row.get("severity"),
        "title": row.get("title"),
        "message": row.get("message"),
        "evidence": row.get("evidence") or {},
        "confidence": float(row.get("confidence") or 0),
        "status": row.get("status"),
        "predictedAt": row.get("predicted_at"),
        "dismissedAt": row.get("dismissed_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _build_predictive_alerts(
    client: Any,
    settings: Settings,
    org_id: str,
    workflow_id: str,
    definition: dict[str, Any],
    *,
    environment_name: str,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    requirements = extract_step_requirements(definition)
    seen_auth: set[str] = set()
    seen_rate: set[str] = set()

    for req in requirements:
        connector_id = req.get("connectorId")
        connector_type = req.get("connectorType")
        # FRED / NVD / CISA KEV / … are Marketplace knowledge-base packs (platform keys),
        # not tenant Connectors-hub products — never emit connector_missing for them.
        if connector_type and is_knowledge_base_source(str(connector_type)):
            continue
        if connector_type and not connector_id:
            connector_id = _find_active_connector_id(
                client, org_id, connector_type, environment_name=environment_name
            )
            if not connector_id:
                if not requires_tenant_connector(str(connector_type)):
                    continue
                from app.intelligence_packs.shared.auth_mode import canonical_connector_vendor

                canon_type = canonical_connector_vendor(str(connector_type)) or str(connector_type)
                mode = get_auth_mode(canon_type)
                display = canon_type.replace("_", " ")
                if mode == AuthMode.BYO_REQUIRED:
                    title = f"Missing {display} credential"
                    message = (
                        f"Step '{req['stepName']}' requires your {display} API key "
                        f"(bring-your-own) but none is connected. Add it from Connectors."
                    )
                else:
                    title = f"Missing {display} connector"
                    message = (
                        f"Step '{req['stepName']}' requires an active {display} connector "
                        f"but none is connected. Add it from Connectors."
                    )
                alerts.append(
                    _alert_row(
                        org_id=org_id,
                        workflow_id=workflow_id,
                        alert_type="connector_missing",
                        severity="critical",
                        title=title,
                        message=message,
                        evidence={
                            "connectorType": canon_type,
                            "connectorTypeRaw": connector_type,
                            "stepName": req["stepName"],
                            "authMode": mode.value,
                        },
                        step_id=req["stepId"],
                    )
                )
                continue

        if connector_id and connector_id not in seen_auth:
            seen_auth.add(connector_id)
            connector = _get_connector(client, org_id, connector_id)
            if connector:
                vendor = str(connector.get("vendor") or connector.get("type") or "")
                auth_status = resolve_connector_auth_status(
                    client,
                    org_id,
                    connector_id,
                    vendor,
                    settings,
                    environment_name=environment_name,
                )
                if auth_status in {"pending_auth", "auth_expired", "misconfigured"}:
                    alerts.append(
                        _alert_row(
                            org_id=org_id,
                            workflow_id=workflow_id,
                            alert_type="auth_disconnected",
                            severity="critical",
                            title=f"{vendor or connector_type or 'Connector'} authentication required",
                            message=(
                                f"Connector auth status is '{auth_status}'. "
                                f"Workflow step '{req['stepName']}' is likely to fail on the next run."
                            ),
                            evidence={
                                "authStatus": auth_status,
                                "connectorType": connector.get("type"),
                                "stepName": req["stepName"],
                            },
                            step_id=req["stepId"],
                            connector_id=connector_id,
                        )
                    )
                else:
                    hours_left = _load_token_expiry_hours(client, settings, connector_id)
                    if hours_left is not None and hours_left <= AUTH_EXPIRY_HIGH_HOURS:
                        severity = "critical" if hours_left <= AUTH_EXPIRY_CRITICAL_HOURS else "high"
                        tokens = load_oauth_tokens(client, connector_id, settings) or {}
                        alerts.append(
                            _alert_row(
                                org_id=org_id,
                                workflow_id=workflow_id,
                                alert_type="auth_expiry",
                                severity=severity,
                                title="OAuth token expiring soon",
                                message=(
                                    f"Connector token expires in {max(int(hours_left), 0)} hours. "
                                    f"Step '{req['stepName']}' may fail when the token expires."
                                ),
                                evidence={
                                    "hoursUntilExpiry": round(hours_left, 2),
                                    "connectorType": connector.get("type"),
                                    "needsRefresh": token_needs_refresh(tokens),
                                },
                                step_id=req["stepId"],
                                connector_id=connector_id,
                            )
                        )

        action = req.get("action")
        agent_id = req.get("agentId")
        if agent_id and action:
            if not _agent_has_scope(
                client,
                org_id,
                agent_id,
                action,
                connector_id,
                connector_type,
            ):
                alerts.append(
                    _alert_row(
                        org_id=org_id,
                        workflow_id=workflow_id,
                        alert_type="missing_scope",
                        severity="high",
                        title="Agent missing tool permission",
                        message=(
                            f"Agent {agent_id} lacks scopes for '{action}' on step '{req['stepName']}'."
                        ),
                        evidence={
                            "agentId": agent_id,
                            "action": action,
                            "requiredScopes": required_scopes_for_action(action),
                            "connectorType": connector_type,
                        },
                        step_id=req["stepId"],
                        connector_id=connector_id,
                    )
                )

        rate_key = f"{req['stepId']}:{connector_type or ''}"
        if rate_key not in seen_rate and connector_type:
            seen_rate.add(rate_key)

    step_rows = _recent_run_steps(client, org_id, workflow_id)
    if step_rows:
        by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in step_rows:
            by_step[str(row.get("step_id") or "")].append(row)

        cutoff_recent = _now() - timedelta(days=3)
        cutoff_prior = _now() - timedelta(days=7)

        for step_id, rows in by_step.items():
            if not step_id:
                continue
            attempts = len(rows)
            failures = len([row for row in rows if row.get("status") == "failed"])
            if attempts >= MIN_RUNS_FOR_STEP_FAILURE:
                failure_rate = failures / attempts
                if failure_rate >= STEP_FAILURE_MEDIUM_RATE:
                    severity = "high" if failure_rate >= STEP_FAILURE_HIGH_RATE else "medium"
                    step_name = next((row.get("step_name") for row in rows if row.get("step_name")), step_id)
                    alerts.append(
                        _alert_row(
                            org_id=org_id,
                            workflow_id=workflow_id,
                            alert_type="step_failure_risk",
                            severity=severity,
                            title=f"Elevated failure rate on '{step_name}'",
                            message=(
                                f"Step failed in {failures}/{attempts} recent runs "
                                f"({round(failure_rate * 100, 1)}%)."
                            ),
                            evidence={
                                "stepName": step_name,
                                "recentAttempts": attempts,
                                "recentFailures": failures,
                                "failureRate": round(failure_rate, 3),
                            },
                            step_id=step_id,
                        )
                    )

            rate_recent = 0
            rate_prior = 0
            for row in rows:
                if not _is_rate_limit_error(row.get("error_message"), row.get("error_code")):
                    continue
                ts_raw = row.get("completed_at") or row.get("created_at") or row.get("run_created_at")
                if not ts_raw:
                    continue
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if ts >= cutoff_recent:
                    rate_recent += 1
                elif ts >= cutoff_prior:
                    rate_prior += 1
            if rate_recent >= 2 and rate_recent > rate_prior:
                step_name = next((row.get("step_name") for row in rows if row.get("step_name")), step_id)
                alerts.append(
                    _alert_row(
                        org_id=org_id,
                        workflow_id=workflow_id,
                        alert_type="rate_limit_trend",
                        severity="high",
                        title=f"Rate limit trend on '{step_name}'",
                        message=(
                            f"Detected {rate_recent} rate-limit failures in the last 3 days "
                            f"vs {rate_prior} in the prior 4 days."
                        ),
                        evidence={
                            "stepName": step_name,
                            "recentRateLimitFailures": rate_recent,
                            "priorRateLimitFailures": rate_prior,
                        },
                        step_id=step_id,
                    )
                )

    return alerts


def _resolve_failure_correlation_keys(
    client: Any,
    *,
    org_id: str,
    run_id: str | None,
    workflow_id: str | None,
    integration: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (workflow_id, connector_id, action_type, integration)."""
    resolved_workflow_id = str(workflow_id or "").strip() or None
    connector_id: str | None = None
    action_type: str | None = None
    resolved_integration = str(integration or "").strip() or None
    if not run_id:
        return resolved_workflow_id, connector_id, action_type, resolved_integration
    try:
        row = (
            client.table("workflow_runs")
            .select("workflow_id,parameters,definition_snapshot")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        data = (row.data or [{}])[0]
        if not resolved_workflow_id:
            resolved_workflow_id = str(data.get("workflow_id") or "").strip() or None
        params = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}
        connector_id = (
            str(params.get("connector_id") or params.get("connectorId") or "").strip() or None
        )
        if not resolved_integration:
            resolved_integration = (
                str(params.get("integration") or params.get("vendor") or "").strip() or None
            )
        definition = (
            data.get("definition_snapshot")
            if isinstance(data.get("definition_snapshot"), dict)
            else {}
        )
        for step in definition.get("steps") or []:
            if not isinstance(step, dict):
                continue
            config = safe_normalize_stored_dict(step, key='config')
            step_type = str(step.get("type") or "").strip()
            action = str(
                config.get("action") or STEP_TYPE_TO_ACTION.get(step_type) or step_type or ""
            ).strip()
            if action and not action_type:
                action_type = action
            cid = str(config.get("connector_id") or config.get("connectorId") or "").strip()
            if cid and not connector_id:
                connector_id = cid
            if action and "." in action and not resolved_integration:
                resolved_integration = action.split(".", 1)[0]
            if connector_id and action_type:
                break
    except Exception as exc:  # noqa: BLE001
        logger.debug("failure_alert_correlate_keys_skipped run=%s err=%s", run_id, exc)
    return resolved_workflow_id, connector_id, action_type, resolved_integration


def _open_observed_alerts(client: Any, *, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        existing = (
            client.table("workflow_failure_alerts")
            .select("id, workflow_id, connector_id, evidence, title, message")
            .eq("org_id", org_id)
            .eq("status", "open")
            .eq("alert_type", "step_failure_risk")
            .order("predicted_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(existing.data or [])
    except Exception as exc:  # noqa: BLE001
        if _is_missing_table_error(exc):
            return []
        logger.debug("failure_alert_list_open_skipped org=%s err=%s", org_id, exc)
        return []


def _alert_matches_correlation(
    row: dict[str, Any],
    *,
    run_id: str | None,
    connector_id: str | None,
    action_type: str | None,
    workflow_id: str | None,
) -> str | None:
    """Return match kind: same_run | connector | action | workflow | None."""
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    if not ev.get("observed_run_failure"):
        return None
    run_ids = {str(ev.get("run_id") or "")}
    run_ids.update(str(x) for x in (ev.get("correlated_run_ids") or []) if x)
    if run_id and str(run_id) in run_ids:
        return "same_run"
    row_connector = str(row.get("connector_id") or ev.get("connector_id") or "").strip()
    if connector_id and row_connector and row_connector == str(connector_id):
        return "connector"
    ev_action = str(ev.get("action_type") or "").strip()
    if action_type and ev_action and ev_action == str(action_type):
        return "action"
    if workflow_id and str(row.get("workflow_id") or "") == str(workflow_id):
        return "workflow"
    return None


def correlate_observed_run_failure(
    client: Any,
    *,
    org_id: str,
    workflow_id: str | None,
    run_id: str | None,
    error_summary: str | None = None,
    source: str | None = None,
    connector_id: str | None = None,
    action_type: str | None = None,
    integration: str | None = None,
) -> bool:
    """Subscriber for Module A: react to a real terminal failure (not a heuristic scan).

    Correlates by workflow_id (legacy), and also by connector_id / action_type so
    vendor outages spanning multiple workflows collapse into one open signal.
    Returns False when correlation is not applicable (no workflow_id to anchor insert).
    """
    (
        resolved_workflow_id,
        resolved_connector_id,
        resolved_action_type,
        resolved_integration,
    ) = _resolve_failure_correlation_keys(
        client,
        org_id=org_id,
        run_id=run_id,
        workflow_id=workflow_id,
        integration=integration,
    )
    if connector_id:
        resolved_connector_id = str(connector_id).strip() or resolved_connector_id
    if action_type:
        resolved_action_type = str(action_type).strip() or resolved_action_type

    open_alerts = _open_observed_alerts(client, org_id=org_id)
    for row in open_alerts:
        kind = _alert_matches_correlation(
            row,
            run_id=run_id,
            connector_id=resolved_connector_id,
            action_type=resolved_action_type,
            workflow_id=resolved_workflow_id,
        )
        if kind == "same_run":
            return True
        if kind in {"connector", "action", "workflow"}:
            ev = safe_normalize_stored_dict(row, key='evidence')
            correlated_runs = [
                str(x) for x in (ev.get("correlated_run_ids") or []) if str(x).strip()
            ]
            if run_id and str(run_id) not in correlated_runs and str(run_id) != str(ev.get("run_id") or ""):
                correlated_runs.append(str(run_id))
            correlated_wfs = [
                str(x) for x in (ev.get("correlated_workflow_ids") or []) if str(x).strip()
            ]
            if resolved_workflow_id and str(resolved_workflow_id) not in correlated_wfs:
                if str(row.get("workflow_id") or "") != str(resolved_workflow_id):
                    correlated_wfs.append(str(resolved_workflow_id))
            all_run_ids = {str(x) for x in correlated_runs if x}
            if ev.get("run_id"):
                all_run_ids.add(str(ev["run_id"]))
            if run_id:
                all_run_ids.add(str(run_id))
            ev.update(
                {
                    "observed_run_failure": True,
                    "correlated_run_ids": correlated_runs[-25:],
                    "correlated_workflow_ids": correlated_wfs[-25:],
                    "failure_count": len(all_run_ids),
                    "connector_id": resolved_connector_id or ev.get("connector_id"),
                    "action_type": resolved_action_type or ev.get("action_type"),
                    "integration": resolved_integration or ev.get("integration"),
                    "correlation_key": (
                        f"connector:{resolved_connector_id}"
                        if resolved_connector_id
                        else (
                            f"action:{resolved_action_type}"
                            if resolved_action_type
                            else f"workflow:{resolved_workflow_id}"
                        )
                    ),
                    "last_correlated_at": _now_iso(),
                    "last_error_summary": (error_summary or "")[:500],
                    "subscriber": "finalize_execution_outcome",
                }
            )
            label = resolved_integration or resolved_action_type or "workflow"
            from app.services.gravitre_voice import format_operator_message

            title = format_operator_message(
                "failure_alert_title",
                label=label,
                repeated=bool(kind in {"connector", "action"} and correlated_wfs),
            )
            message = format_operator_message(
                "failure_alert_body",
                blocker=(error_summary or "run failed")[:400],
                failure_count=len(correlated_runs) + 1,
            )
            try:
                client.table("workflow_failure_alerts").update(
                    {
                        "evidence": ev,
                        "title": title[:200],
                        "message": message,
                        "severity": "critical" if len(correlated_runs) >= 2 else "high",
                        "connector_id": resolved_connector_id or row.get("connector_id"),
                        "updated_at": _now_iso(),
                    }
                ).eq("id", row["id"]).eq("org_id", org_id).execute()
                return True
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "failure_alert_correlate_merge_skipped alert=%s err=%s",
                    row.get("id"),
                    exc,
                )
                break

    if not resolved_workflow_id:
        # Chat orch / assignment runs without workflow_defs FK cannot insert
        # (workflow_id NOT NULL). Learning + Runs/Notifications/Audit still fan out.
        return False

    evidence = {
        "observed_run_failure": True,
        "run_id": run_id,
        "source": source,
        "error_summary": (error_summary or "")[:500],
        "correlated_at": _now_iso(),
        "subscriber": "finalize_execution_outcome",
        "connector_id": resolved_connector_id,
        "action_type": resolved_action_type,
        "integration": resolved_integration,
        "correlated_run_ids": [],
        "correlated_workflow_ids": [],
        "failure_count": 1,
        "correlation_key": (
            f"connector:{resolved_connector_id}"
            if resolved_connector_id
            else (
                f"action:{resolved_action_type}"
                if resolved_action_type
                else f"workflow:{resolved_workflow_id}"
            )
        ),
    }
    label = resolved_integration or resolved_action_type or "workflow"
    from app.services.gravitre_voice import format_operator_message

    alert = _alert_row(
        org_id=org_id,
        workflow_id=resolved_workflow_id,
        alert_type="step_failure_risk",
        severity="high",
        title=format_operator_message("failure_alert_title", label=label, repeated=False),
        message=format_operator_message(
            "failure_alert_body",
            blocker=(error_summary or "A workflow run failed. Review the run for step-level errors.")[
                :400
            ],
            failure_count=1,
        ),
        evidence=evidence,
        connector_id=resolved_connector_id,
    )
    try:
        client.table("workflow_failure_alerts").insert(alert).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        if _is_missing_table_error(exc):
            return False
        logger.debug(
            "failure_alert_correlate_skipped org=%s workflow=%s run=%s err=%s",
            org_id,
            resolved_workflow_id,
            run_id,
            exc,
        )
        return False


def list_failure_alerts(
    client: Any,
    org_id: str,
    *,
    workflow_id: str | None = None,
    status: str = "open",
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = (
        client.table("workflow_failure_alerts")
        .select("*")
        .eq("org_id", org_id)
        .eq("status", status)
        .order("predicted_at", desc=True)
        .limit(limit)
    )
    if workflow_id:
        query = query.eq("workflow_id", workflow_id)
    try:
        result = query.execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise
    if _is_missing_table_error(getattr(result, "error", None)):
        return []
    return [_serialize_alert(row) for row in (result.data or [])]


def dismiss_failure_alert(client: Any, org_id: str, alert_id: str) -> dict[str, Any]:
    existing = (
        client.table("workflow_failure_alerts")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", alert_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise FailurePredictionError("Alert not found", code="ALERT_NOT_FOUND")
    now = _now_iso()
    updated = (
        client.table("workflow_failure_alerts")
        .update({"status": "dismissed", "dismissed_at": now})
        .eq("org_id", org_id)
        .eq("id", alert_id)
        .execute()
    )
    row = (updated.data or existing.data)[0]
    return _serialize_alert(row)


def scan_workflow_failure_predictions(
    client: Any,
    settings: Settings,
    org_id: str,
    workflow_id: str,
    *,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Run heuristics, persist open alerts, return scan summary."""
    definition = _resolve_workflow_definition(client, org_id, workflow_id, environment_name=environment_name)
    alerts = _build_predictive_alerts(
        client,
        settings,
        org_id,
        workflow_id,
        definition,
        environment_name=environment_name,
    )

    try:
        client.table("workflow_failure_alerts").delete().eq("org_id", org_id).eq(
            "workflow_id", workflow_id
        ).eq("status", "open").execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning(
                "workflow_failure_alerts missing; skipping persist org_id=%s workflow_id=%s",
                org_id,
                workflow_id,
            )
            return {
                "workflowId": workflow_id,
                "alertCount": len(alerts),
                "riskScore": _compute_risk_score(alerts),
                "alerts": alerts,
                "scannedAt": _now_iso(),
                "environment": environment_name,
            }
        raise

    persisted: list[dict[str, Any]] = []
    if alerts:
        try:
            insert_result = client.table("workflow_failure_alerts").insert(alerts).execute()
            persisted = [_serialize_alert(row) for row in (insert_result.data or alerts)]
        except Exception as exc:
            if _is_missing_table_error(exc):
                persisted = alerts
            else:
                raise

    risk_score = _compute_risk_score(alerts)
    summary = {
        "workflowId": workflow_id,
        "alertCount": len(persisted),
        "riskScore": risk_score,
        "alerts": persisted,
        "scannedAt": _now_iso(),
        "environment": environment_name,
    }

    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_FAILURE_PREDICTION_SCANNED,
            RESOURCE_TYPE_WORKFLOW_FAILURE_ALERT,
            workflow_id,
            metadata={
                "alertCount": len(persisted),
                "riskScore": risk_score,
                "alertTypes": list({alert["alertType"] for alert in persisted}),
            },
        )

    logger.info(
        "workflow_failure_prediction_scan org_id=%s workflow_id=%s alerts=%s risk=%s",
        org_id,
        workflow_id,
        len(persisted),
        risk_score,
    )
    return summary


def scan_org_failure_predictions(
    client: Any,
    settings: Settings,
    org_id: str,
    *,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Run heuristic pre-failure scans for every org workflow (STA-167)."""
    workflows = list_workflows(client, org_id)
    candidates = [
        row
        for row in workflows
        if str(row.get("status") or "").lower() not in {"archived", "deleted"}
    ]

    workflow_summaries: list[dict[str, Any]] = []
    all_alerts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for workflow in candidates:
        workflow_id = str(workflow.get("id") or "")
        if not workflow_id:
            continue
        try:
            summary = scan_workflow_failure_predictions(
                client,
                settings,
                org_id,
                workflow_id,
                environment_name=environment_name,
            )
        except FailurePredictionError as exc:
            errors.append(
                {
                    "workflowId": workflow_id,
                    "workflowName": workflow.get("name"),
                    "code": exc.code,
                    "message": str(exc),
                }
            )
            continue

        alerts = summary.get("alerts") or []
        workflow_summaries.append(
            {
                "workflowId": workflow_id,
                "workflowName": workflow.get("name"),
                "alertCount": summary.get("alertCount", len(alerts)),
                "riskScore": summary.get("riskScore", 0),
            }
        )
        all_alerts.extend(alerts)

    risk_score = _compute_risk_score(all_alerts)
    summary = {
        "workflowCount": len(candidates),
        "scannedCount": len(workflow_summaries),
        "alertCount": len(all_alerts),
        "riskScore": risk_score,
        "workflows": workflow_summaries,
        "alerts": all_alerts,
        "errors": errors,
        "scannedAt": _now_iso(),
        "environment": environment_name,
    }

    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_FAILURE_PREDICTION_SCANNED,
            RESOURCE_TYPE_WORKFLOW_FAILURE_ALERT,
            org_id,
            metadata={
                "scope": "org",
                "workflowCount": len(candidates),
                "scannedCount": len(workflow_summaries),
                "alertCount": len(all_alerts),
                "riskScore": risk_score,
                "errorCount": len(errors),
            },
        )

    logger.info(
        "workflow_failure_prediction_org_scan org_id=%s workflows=%s alerts=%s risk=%s errors=%s",
        org_id,
        len(workflow_summaries),
        len(all_alerts),
        risk_score,
        len(errors),
    )
    return summary
