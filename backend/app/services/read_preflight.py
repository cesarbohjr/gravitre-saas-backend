"""Canonical F1 READ preflight — compile ActionSpec before any provider call."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.connectors.action_catalog.f1_read_slice import (
    catalog_action_key,
    is_f1_read_action,
    registry_action_key,
)
from app.connectors.action_catalog.models import ActionSpec, ParameterSourceRule
from app.connectors.action_catalog.registry import get_action_spec
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.canonical_time_resolver import TimeWindow, resolve_time_window, time_window_from_mapping
from app.services.connector_resource_resolver import ResourceResolution, resolve_resource
from app.services.domain_property_binding import match_resource_to_domain
from app.services.org_business_identity import merge_business_identity
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.tool_types import ToolContext, ToolValidationError

logger = get_logger(__name__)

PREFLIGHT_ERROR_CLASSES = frozenset(
    {
        "RESOURCE_UNRESOLVED",
        "PARAMETER_UNRESOLVED",
        "AUTH_UNAVAILABLE",
        "NOT_CONFIGURED",
        "NOT_AUTHENTICATED",
        "AUTH_EXPIRED",
        "MISSING_SCOPE",
        "ACTION_UNAVAILABLE",
        "SCHEMA_INVALID",
        "PROVIDER_CONSTRAINT_INVALID",
        "PERMISSION_BLOCKED",
        "TENANT_SCOPE_VIOLATION",
        "WRONG_SIBLING_ACTION",
        "PREFLIGHT_REQUIRED",
        "PREFLIGHT_STALE",
        "GENUINE_USER_CLARIFICATION_REQUIRED",
    }
)

_USER_FACING = {
    "RESOURCE_UNRESOLVED": "I couldn't identify which account or property to read.",
    "PARAMETER_UNRESOLVED": "I need one more business detail before I can look that up.",
    "AUTH_UNAVAILABLE": "This connection needs to be re-authorized before I can read data.",
    "NOT_CONFIGURED": "That data source isn't connected for this workspace.",
    "NOT_AUTHENTICATED": "This connection isn't signed in yet.",
    "AUTH_EXPIRED": "This connection's sign-in expired and needs to be refreshed.",
    "MISSING_SCOPE": "This connection is missing permission to read that data.",
    "ACTION_UNAVAILABLE": "That data source isn't connected for this workspace.",
    "SCHEMA_INVALID": "The request isn't valid for this read.",
    "PROVIDER_CONSTRAINT_INVALID": "The request doesn't meet the provider's read constraints.",
    "PERMISSION_BLOCKED": "This read isn't permitted for the current workspace.",
    "TENANT_SCOPE_VIOLATION": "That resource isn't available in this workspace.",
    "WRONG_SIBLING_ACTION": "I need a different kind of lookup for that request.",
    "PREFLIGHT_REQUIRED": "That read wasn't compiled before execution.",
    "PREFLIGHT_STALE": "The compiled read no longer matches this request.",
    "GENUINE_USER_CLARIFICATION_REQUIRED": "I need you to choose among a few valid options.",
}

_UNTRUSTED_MARKERS = (
    "_preflight_ok",
    "_preflight_token",
    "preflight_ok",
    "preflight_token",
    "preflightResult",
)

_PROOF_SECRET = secrets.token_bytes(32)
_RESOURCE_PARAMS = {"property_id", "site_url", "portal_id", "realm_id", "subdomain"}
_SEARCH_HINT = re.compile(r"(?i)\b(high[- ]value|amount|stage|pipeline|won|lost|closed)\b")


@dataclass(frozen=True)
class ParameterProvenance:
    parameter: str
    source: str
    value: Any
    confidence: float | None = None
    classification: str = "FILLED"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parameter": self.parameter,
            "source": self.source,
            "value": self.value,
            "classification": self.classification,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass
class PreflightResult:
    status: str
    plan_id: str | None = None
    step_id: str | None = None
    action_key: str = ""
    connector_id: str = ""
    resource: dict[str, Any] | None = None
    compiled_parameters: dict[str, Any] = field(default_factory=dict)
    parameter_provenance: list[ParameterProvenance] = field(default_factory=list)
    schema_validation: str = "not_run"
    provider_constraint_validation: str = "not_run"
    auth_validation: str = "not_run"
    availability_validation: str = "not_run"
    blocking_reason: str | None = None
    repair_hint: str | None = None
    error_class: str | None = None
    duration_ms: int = 0
    token: str | None = None
    proposed_args: dict[str, Any] = field(default_factory=dict)
    shadow_diff: dict[str, Any] | None = None
    time_window: dict[str, str] | None = None
    capability_id: str | None = None
    provider_invoked: bool = False
    org_id: str = ""
    spec_revision: str = ""
    proof_digest: str | None = None
    turn_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ready"

    def user_message(self) -> str:
        if self.ok:
            return ""
        return _USER_FACING.get(self.error_class or "", "I couldn't complete that read yet.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "action_key": self.action_key,
            "connector_id": self.connector_id,
            "resource": self.resource,
            "compiled_parameters": dict(self.compiled_parameters),
            "parameter_provenance": [p.as_dict() for p in self.parameter_provenance],
            "schema_validation": self.schema_validation,
            "provider_constraint_validation": self.provider_constraint_validation,
            "auth_validation": self.auth_validation,
            "availability_validation": self.availability_validation,
            "blocking_reason": self.blocking_reason,
            "repair_hint": self.repair_hint,
            "error_class": self.error_class,
            "duration_ms": self.duration_ms,
            "capability_id": self.capability_id,
            "time_window": self.time_window,
        }

    def safe_parameter_summary(self) -> dict[str, Any]:
        blocked = {"token", "secret", "password", "authorization", "api_key"}
        return {
            key: value
            for key, value in self.compiled_parameters.items()
            if not any(part in key.lower() for part in blocked)
        }


def _cache_action_spec(action_key: str) -> ActionSpec | None:
    return get_action_spec(catalog_action_key(action_key)) or get_action_spec(action_key)


def _first_present(payload: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in payload and payload[name] not in (None, ""):
            return payload[name]
    return None


def business_identity_from_context(context: dict[str, Any] | None) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    return merge_business_identity(
        org_id=str(ctx.get("org_id") or ""),
        context=ctx,
        user_message=str(ctx.get("user_message") or ctx.get("message") or ""),
        client=ctx.get("client"),
        environment_name=str(ctx.get("environment_name") or "production"),
    )


def _blocked(
    *,
    error_class: str,
    reason: str,
    repair_hint: str,
    started: float,
    result: PreflightResult,
) -> PreflightResult:
    result.status = "blocked"
    result.error_class = error_class
    result.blocking_reason = reason
    result.repair_hint = repair_hint
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def _pick_from_source(
    source: str,
    rule: ParameterSourceRule,
    *,
    proposed: dict[str, Any],
    task_state: dict[str, Any],
    identity: dict[str, Any],
    resource: ResourceResolution | None,
    time_window: TimeWindow | None,
    connector_row: dict[str, Any] | None,
) -> tuple[Any, float] | None:
    names = (rule.parameter, *rule.aliases)
    if source == "USER_EXPLICIT":
        value = _first_present(proposed, names)
        if value is None:
            return None
        if rule.parameter in _RESOURCE_PARAMS:
            return None
        if rule.parameter in {"start_date", "end_date"} and time_window is not None:
            expected = time_window.start_iso if rule.parameter == "start_date" else time_window.end_iso
            if str(value).strip() != expected:
                return None
        return value, 1.0
    if source == "MODEL_INFERENCE":
        value = _first_present(proposed, names)
        if value is None:
            return None
        if rule.parameter in _RESOURCE_PARAMS:
            if resource and resource.status == "resolved" and str(value).strip() == str(resource.resource_id).strip():
                return value, 0.4
            return None
        if rule.parameter in {"start_date", "end_date"} and time_window is not None:
            return None
        return value, 0.35
    if source == "TASK_CONTEXT":
        buckets = [
            task_state,
            task_state.get("connector_session") if isinstance(task_state.get("connector_session"), dict) else {},
            (task_state.get("connector_session") or {}).get("resolvedEntities")
            if isinstance(task_state.get("connector_session"), dict)
            else {},
        ]
        for bucket in buckets:
            if isinstance(bucket, dict):
                value = _first_present(bucket, names)
                if value is not None:
                    return value, 0.85
        return None
    if source == "REFERENCE_STATE":
        referent = task_state.get("active_analysis") if isinstance(task_state.get("active_analysis"), dict) else {}
        value = _first_present(referent, names)
        return (value, 0.8) if value is not None else None
    if source == "RESOURCE_RESOLVER" and resource and resource.status == "resolved":
        prior = float(resource.confidence or 0.9)  # confidence-honesty-ok: resolver prior, not user-facing
        return resource.resource_id, prior
    if source == "CONNECTOR_METADATA" and isinstance(connector_row, dict):
        cfg = connector_row.get("config") if isinstance(connector_row.get("config"), dict) else {}
        value = _first_present({**connector_row, **cfg}, names)
        return (value, 0.92) if value is not None else None
    if source == "BUSINESS_IDENTITY":
        # Website identity maps to GSC site_url only — never to a GA4 property_id.
        if rule.parameter == "site_url" and identity.get("website"):
            return identity["website"], 0.6
        value = _first_present(identity, names)
        if value is not None and rule.parameter != "website":
            return value, 0.6
        return None
    if source == "TIME_RESOLVER" and time_window is not None:
        if rule.parameter == "start_date":
            return time_window.start_iso, 0.99
        if rule.parameter == "end_date":
            return time_window.end_iso, 0.99
        return None
    if source == "CAPABILITY_RECIPE" and rule.default is not None:
        return rule.default, 0.7
    if source == "ACTION_DEFAULT" and rule.default is not None:
        return rule.default, 0.5
    if source == "PREVIOUS_OBSERVATION":
        obs = task_state.get("last_observation") if isinstance(task_state.get("last_observation"), dict) else {}
        value = _first_present(obs, names)
        return (value, 0.75) if value is not None else None
    return None


def _validate_constraints(spec: ActionSpec, compiled: dict[str, Any]) -> str | None:
    constraints = spec.provider_constraints or {}
    if constraints.get("date_order") == "start_lte_end":
        start = str(compiled.get("start_date") or "")
        end = str(compiled.get("end_date") or "")
        if start and end and start > end:
            return "start_date after end_date"
    limit_max = constraints.get("limit_max")
    if limit_max is not None and "limit" in compiled:
        try:
            if int(compiled["limit"]) > int(limit_max) or int(compiled["limit"]) < 1:
                return "limit out of range"
        except (TypeError, ValueError):
            return "limit not an integer"
    return None


def strip_untrusted_preflight_markers(params: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(params)
    for key in _UNTRUSTED_MARKERS:
        cleaned.pop(key, None)
    return cleaned


def _classify_auth(resolution: ResourceResolution) -> str:
    reason = str(resolution.resolution_reason or "").lower()
    if resolution.status == "not_found" or "not_configured" in reason or "connector_not_configured" in reason:
        return "NOT_CONFIGURED"
    if "invalid_grant" in reason or "expired" in reason or "token_expired" in reason:
        return "AUTH_EXPIRED"
    if "scope" in reason:
        return "MISSING_SCOPE"
    if resolution.status == "not_authorized" or "auth" in reason:
        return "NOT_AUTHENTICATED"
    return "AUTH_UNAVAILABLE"


def _has_search_criteria(proposed: dict[str, Any], message: str) -> bool:
    if proposed.get("filter_groups") or proposed.get("filterGroups"):
        return True
    if str(proposed.get("query") or "").strip():
        return True
    return bool(_SEARCH_HINT.search(message or ""))


def _cross_tenant_attempt(
    proposed: dict[str, Any],
    resolution: ResourceResolution | None,
    org_id: str,
) -> bool:
    if resolution is None:
        return False
    hinted = str(proposed.get("property_id") or proposed.get("site_url") or proposed.get("resource_id") or "").strip()
    if not hinted:
        return False
    for raw in resolution.candidates or ():
        if not isinstance(raw, dict):
            continue
        candidate_id = str(raw.get("property_id") or raw.get("site_url") or raw.get("resource_id") or "").strip()
        candidate_org = str(raw.get("org_id") or raw.get("tenant_id") or "").strip()
        if candidate_id == hinted and candidate_org and candidate_org != str(org_id):
            return True
    return False


def _repair_class(parameter: str, source: str, proposed: dict[str, Any], value: Any) -> str:
    original = proposed.get(parameter)
    if original in (None, ""):
        return f"FILLED_FROM_{source}"
    if original == value:
        return "NORMALIZED" if source != "MODEL_INFERENCE" else "FILLED"
    if source == "TIME_RESOLVER":
        return "OVERRIDDEN_BY_TIME_RESOLVER"
    if source == "RESOURCE_RESOLVER":
        return "OVERRIDDEN_BY_RESOURCE_RESOLVER"
    return f"OVERRIDDEN_BY_{source}"


def _binding_payload(
    *,
    org_id: str,
    plan_id: str | None,
    step_id: str | None,
    action_key: str,
    connector_id: str,
    resource_id: str,
    compiled: dict[str, Any],
    spec_revision: str,
) -> bytes:
    body = {
        "org_id": org_id,
        "plan_id": plan_id or "",
        "step_id": step_id or "",
        "action_key": catalog_action_key(action_key),
        "connector_id": connector_id,
        "resource_id": resource_id,
        "compiled": compiled,
        "spec_revision": spec_revision,
    }
    return json.dumps(body, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")


def seal_preflight_proof(result: PreflightResult) -> PreflightResult:
    digest = hmac.new(
        _PROOF_SECRET,
        _binding_payload(
            org_id=result.org_id,
            plan_id=result.plan_id,
            step_id=result.step_id,
            action_key=result.action_key,
            connector_id=result.connector_id,
            resource_id=str((result.resource or {}).get("id") or ""),
            compiled=dict(result.compiled_parameters),
            spec_revision=result.spec_revision,
        ),
        hashlib.sha256,
    ).hexdigest()
    result.proof_digest = digest
    result.token = None
    return result


def verify_bound_preflight(ctx: ToolContext, action: str, params: dict[str, Any]) -> PreflightResult:
    proof = getattr(ctx, "preflight_result", None)
    if not isinstance(proof, PreflightResult) or not proof.ok or not proof.proof_digest:
        raise ToolValidationError(
            _USER_FACING["PREFLIGHT_REQUIRED"],
            code="PREFLIGHT_REQUIRED",
        )
    incoming = strip_untrusted_preflight_markers(params)
    for key, value in incoming.items():
        if key.startswith("_"):
            continue
        compiled_value = proof.compiled_parameters.get(key)
        if compiled_value is not None and value not in (None, "") and value != compiled_value:
            raise ToolValidationError(
                _USER_FACING["PREFLIGHT_STALE"],
                code="PREFLIGHT_STALE",
                details={"parameter": key, "repair_hint": "recompile_preflight"},
            )
    current_action = catalog_action_key(action)
    if catalog_action_key(proof.action_key) != current_action:
        raise ToolValidationError(_USER_FACING["PREFLIGHT_STALE"], code="PREFLIGHT_STALE")
    if str(ctx.org_id) != str(proof.org_id):
        raise ToolValidationError(_USER_FACING["PERMISSION_BLOCKED"], code="PERMISSION_BLOCKED")
    spec = get_action_spec(current_action)
    if spec is not None and spec.spec_revision and spec.spec_revision != proof.spec_revision:
        raise ToolValidationError(_USER_FACING["PREFLIGHT_STALE"], code="PREFLIGHT_STALE")
    incoming_resource = str(
        incoming.get("property_id")
        or incoming.get("site_url")
        or incoming.get("portal_id")
        or incoming.get("realm_id")
        or incoming.get("subdomain")
        or ""
    )
    sealed_resource = str((proof.resource or {}).get("id") or "")
    if incoming_resource and sealed_resource and incoming_resource != sealed_resource:
        raise ToolValidationError(_USER_FACING["PREFLIGHT_STALE"], code="PREFLIGHT_STALE")
    expected = hmac.new(
        _PROOF_SECRET,
        _binding_payload(
            org_id=proof.org_id,
            plan_id=proof.plan_id,
            step_id=proof.step_id,
            action_key=proof.action_key,
            connector_id=proof.connector_id,
            resource_id=sealed_resource,
            compiled=dict(proof.compiled_parameters),
            spec_revision=proof.spec_revision,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(str(proof.proof_digest), expected):
        raise ToolValidationError(_USER_FACING["PREFLIGHT_STALE"], code="PREFLIGHT_STALE")
    return proof


def preflight_read_action(
    *,
    execution_plan: ExecutionPlan | dict[str, Any] | None = None,
    execution_step: ExecutionStep | dict[str, Any] | None = None,
    action_spec: ActionSpec | None = None,
    context: dict[str, Any] | None = None,
) -> PreflightResult:
    """Compile CAPABILITY→ACTION→RESOURCE→PARAMETERS→AVAILABILITY→CONSTRAINTS for F1 READ."""
    started = time.perf_counter()
    ctx = dict(context or {})
    proposed = strip_untrusted_preflight_markers(safe_normalize_stored_dict(ctx.get("proposed_args")))
    user_message = str(ctx.get("user_message") or ctx.get("message") or "")
    org_id = str(ctx.get("org_id") or "")
    client = ctx.get("client")
    settings = ctx.get("settings")
    task_state = ctx.get("task_state") if isinstance(ctx.get("task_state"), dict) else {}
    connector_row = ctx.get("connector_row") if isinstance(ctx.get("connector_row"), dict) else None

    plan_id = None
    step_id = None
    action_key = str(ctx.get("action_key") or "")
    capability_id = str(ctx.get("capability_id") or "") or None
    if isinstance(execution_plan, ExecutionPlan):
        plan_id = execution_plan.plan_id
    elif isinstance(execution_plan, dict):
        plan_id = str(execution_plan.get("plan_id") or "") or None
    if isinstance(execution_step, ExecutionStep):
        step_id = execution_step.step_id
        action_key = action_key or str(execution_step.action_key or "")
        capability_id = capability_id or execution_step.capability_id
    elif isinstance(execution_step, dict):
        step_id = str(execution_step.get("step_id") or "") or None
        action_key = action_key or str(execution_step.get("action_key") or "")
    plan_id = plan_id or (str(ctx.get("plan_id") or "").strip() or None)
    step_id = step_id or (str(ctx.get("step_id") or "").strip() or None)

    result = PreflightResult(
        status="blocked",
        plan_id=plan_id,
        step_id=step_id,
        action_key=action_key,
        proposed_args=dict(proposed),
        capability_id=capability_id,
        org_id=org_id,
        turn_id=str(ctx.get("turn_id") or "") or None,
    )

    spec = action_spec or _cache_action_spec(action_key)
    if spec is None or not is_f1_read_action(spec.id):
        return _blocked(
            error_class="ACTION_UNAVAILABLE",
            reason="action_not_in_f1_read_slice" if spec is None else "action_not_f1_read",
            repair_hint="use_catalog_action_key",
            started=started,
            result=result,
        )
    if spec.kind == "write":
        return _blocked(
            error_class="PERMISSION_BLOCKED",
            reason="write_not_in_f1_preflight",
            repair_hint="do_not_use_read_preflight_for_writes",
            started=started,
            result=result,
        )

    result.action_key = spec.id
    result.connector_id = spec.id.split(".", 1)[0]
    result.spec_revision = spec.spec_revision
    if not capability_id and spec.capabilities:
        result.capability_id = spec.capabilities[0]
        capability_id = result.capability_id

    connected = {str(v).lower() for v in (ctx.get("connected_integrations") or []) if str(v).strip()}
    vendor = result.connector_id
    if connected and vendor not in connected and registry_action_key(spec.id).split(".", 1)[0] not in connected:
        result.availability_validation = "failed"
        return _blocked(
            error_class="ACTION_UNAVAILABLE",
            reason="connector_not_connected",
            repair_hint="connect_source",
            started=started,
            result=result,
        )
    result.availability_validation = "passed"
    if spec.id == "hubspot.deals.search" and not _has_search_criteria(proposed, user_message):
        return _blocked(
            error_class="WRONG_SIBLING_ACTION",
            reason="deals.search_requires_structured_criteria",
            repair_hint="use_structured_deal_search_or_list",
            started=started,
            result=result,
        )

    identity = business_identity_from_context({**task_state, **ctx})
    override = ctx.get("time_window_override")
    if isinstance(override, TimeWindow):
        time_window = override
    elif isinstance(override, dict):
        time_window = time_window_from_mapping(override)
    else:
        time_window = resolve_time_window(
            user_message,
            timezone_name=identity.get("timezone"),
            now=ctx.get("now"),
        )
    if time_window:
        result.time_window = time_window.as_dict()

    resource_type = spec.resource_requirements[0] if spec.resource_requirements else None
    conversation_context = {
        **task_state,
        "business_identity": identity,
        "org_id": org_id,
    }
    if connector_row:
        conversation_context["_connector_row"] = connector_row

    resolution: ResourceResolution | None = None
    if client is not None and settings is not None and org_id:
        resolution = resolve_resource(
            connector_id=vendor,
            client=client,
            org_id=org_id,
            settings=settings,
            resource_type=resource_type,
            environment_name=str(ctx.get("environment_name") or "production"),
            conversation_context=conversation_context,
            connector_row=connector_row,
        )
        if (
            resolution.status == "ambiguous"
            and identity.get("host")
            and resolution.candidates
        ):
            matched = match_resource_to_domain(
                resolution.candidates,
                host=str(identity.get("host") or ""),
                org_id=org_id,
            )
            if matched:
                resource_id = str(
                    matched.get("property_id")
                    or matched.get("site_url")
                    or matched.get("resource_id")
                    or ""
                )
                resolution = ResourceResolution(
                    status="resolved",
                    connector_id=resolution.connector_id,
                    connection_id=resolution.connection_id,
                    resource_type=resolution.resource_type,
                    resource_id=resource_id,
                    display_name=str(matched.get("display_name") or matched.get("site_url") or resource_id),
                    confidence=0.9,  # confidence-honesty-ok: domain bind prior, not user-facing
                    resolution_reason="tenant_domain_binding",
                    candidate_count=1,
                    candidates=(matched,),
                )
        if _cross_tenant_attempt(proposed, resolution, org_id):
            result.auth_validation = "failed"
            return _blocked(
                error_class="TENANT_SCOPE_VIOLATION",
                reason="REJECTED_TENANT_SCOPE",
                repair_hint="same_tenant_only",
                started=started,
                result=result,
            )
        if resolution.status == "not_authorized":
            result.auth_validation = "failed"
            return _blocked(
                error_class=_classify_auth(resolution),
                reason=resolution.resolution_reason or "auth_failed",
                repair_hint="reconnect_connector",
                started=started,
                result=result,
            )
        if resolution.status == "ambiguous":
            result.auth_validation = "passed"
            return _blocked(
                error_class="GENUINE_USER_CLARIFICATION_REQUIRED",
                reason="multiple_valid_resources",
                repair_hint="ask_which_resource",
                started=started,
                result=result,
            )
        if resolution.status in {"not_found", "unavailable"} and spec.resource_requirements:
            result.auth_validation = "failed" if resolution.status == "unavailable" else "passed"
            error = (
                _classify_auth(resolution)
                if resolution.status == "not_found" and "connector_not_configured" in str(resolution.resolution_reason)
                else "RESOURCE_UNRESOLVED"
            )
            return _blocked(
                error_class=error,
                reason=resolution.resolution_reason or "resource_unresolved",
                repair_hint="resolve_resource",
                started=started,
                result=result,
            )
        if resolution.status == "resolved":
            result.auth_validation = "passed"
            result.resource = {
                "type": resolution.resource_type,
                "id": resolution.resource_id,
                "name": resolution.display_name,
                "reason": resolution.resolution_reason,
                "connection_id": resolution.connection_id,
            }
        else:
            result.auth_validation = "passed"
    else:
        result.auth_validation = "skipped"

    compiled: dict[str, Any] = {}
    provenance: list[ParameterProvenance] = []
    for rule in spec.parameter_source_rules:
        chosen = None
        source_used = None
        confidence = None
        for source in rule.sources:
            if source == "MUST_ASK_USER":
                continue
            picked = _pick_from_source(
                source,
                rule,
                proposed=proposed,
                task_state=task_state,
                identity=identity,
                resource=resolution,
                time_window=time_window,
                connector_row=connector_row,
            )
            if picked is None:
                continue
            chosen, confidence = picked
            source_used = source
            break
        if chosen is None:
            if rule.required_by_api or rule.required_from_user:
                error = (
                    "GENUINE_USER_CLARIFICATION_REQUIRED"
                    if rule.required_from_user
                    else "PARAMETER_UNRESOLVED"
                )
                return _blocked(
                    error_class=error,
                    reason=f"unresolved:{rule.parameter}",
                    repair_hint="deterministic_sources_exhausted",
                    started=started,
                    result=result,
                )
            continue
        compiled[rule.parameter] = chosen
        provenance.append(
            ParameterProvenance(
                parameter=rule.parameter,
                source=str(source_used),
                value=chosen,
                confidence=confidence,
                classification=_repair_class(rule.parameter, str(source_used), proposed, chosen),
            )
        )

    for key, value in proposed.items():
        if key.startswith("_"):
            continue
        if key not in compiled and value not in (None, ""):
            compiled[key] = value
            provenance.append(
                ParameterProvenance(
                    parameter=key,
                    source="MODEL_INFERENCE",
                    value=value,
                    confidence=0.4,  # confidence-honesty-ok: leftover model arg prior, not user-facing
                    classification="FILLED",
                )
            )

    result.compiled_parameters = compiled
    result.parameter_provenance = provenance

    missing = [name for name in spec.required_parameters if not compiled.get(name)]
    if missing:
        result.schema_validation = "failed"
        return _blocked(
            error_class="SCHEMA_INVALID",
            reason="missing_required_after_compile",
            repair_hint="compile_required_parameters",
            started=started,
            result=result,
        )
    result.schema_validation = "passed"

    constraint_error = _validate_constraints(spec, compiled)
    if constraint_error:
        result.provider_constraint_validation = "failed"
        return _blocked(
            error_class="PROVIDER_CONSTRAINT_INVALID",
            reason=constraint_error,
            repair_hint="fix_provider_constraints",
            started=started,
            result=result,
        )
    result.provider_constraint_validation = "passed"

    shadow = {}
    for key, compiled_value in compiled.items():
        proposed_value = proposed.get(key)
        if proposed_value not in (None, "") and proposed_value != compiled_value:
            shadow[key] = {"proposed": proposed_value, "compiled": compiled_value}
    result.shadow_diff = shadow or None
    if shadow:
        logger.info(
            "f1_preflight_shadow_diff action=%s org=%s diff=%s",
            spec.id,
            org_id,
            json.dumps(shadow, default=str)[:500],
        )

    result.status = "ready"
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    seal_preflight_proof(result)
    logger.info(
        "f1_preflight_ok turn_id=%s plan_id=%s step_id=%s capability_id=%s action_key=%s "
        "connector_id=%s preflight_status=%s preflight_duration_ms=%s provider_invoked=false "
        "resource=%s parameter_sources=%s compiled_parameters_safe_summary=%s",
        ctx.get("turn_id"),
        plan_id,
        step_id,
        capability_id,
        spec.id,
        result.connector_id,
        result.status,
        result.duration_ms,
        (result.resource or {}).get("id"),
        [p.source for p in provenance],
        result.safe_parameter_summary(),
    )
    return result


def apply_preflight_to_params(params: dict[str, Any], result: PreflightResult) -> dict[str, Any]:
    cleaned = strip_untrusted_preflight_markers(params)
    merged = dict(cleaned)
    merged.update(result.compiled_parameters)
    return merged


def enforce_invoke_preflight(ctx: ToolContext, action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Refuse F1 READ provider execution unless a bound internal PreflightResult matches."""
    params = strip_untrusted_preflight_markers(params)
    if not is_f1_read_action(action):
        return params
    proof = verify_bound_preflight(ctx, action, params)
    return apply_preflight_to_params(params, proof)


def react_preflight_args(
    *,
    ctx: ToolContext,
    invoke_action: str,
    args: dict[str, Any] | None,
    user_message: str,
    connected_integrations: list[str] | None = None,
) -> tuple[dict[str, Any], PreflightResult | None]:
    """ReAct may propose args; canonical preflight compiles/repairs before invoke."""
    proposed = strip_untrusted_preflight_markers(dict(args or {}))
    if not is_f1_read_action(invoke_action):
        return proposed, None
    result = preflight_read_action(
        action_spec=_cache_action_spec(invoke_action),
        context={
            "action_key": catalog_action_key(invoke_action),
            "org_id": ctx.org_id,
            "client": ctx.client,
            "settings": ctx.settings,
            "proposed_args": proposed,
            "user_message": user_message,
            "environment_name": ctx.environment_name,
            "connected_integrations": connected_integrations,
            "turn_id": getattr(ctx, "turn_id", None) or getattr(ctx, "conversation_id", None),
            "plan_id": getattr(ctx, "plan_id", None),
            "step_id": getattr(ctx, "step_id", None),
            "capability_id": getattr(ctx, "capability_id", None),
        },
    )
    if not result.ok:
        return proposed, result
    return dict(result.compiled_parameters), result
