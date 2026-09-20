"""Phase 2.0-F — compile governed WRITEs with the F1 ActionSpec contract.

Approval is not granted here. HMAC binds compiled parameters so invoke cannot
use a different payload than the one shown at confirm.
"""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.f1_read_slice import catalog_action_key, registry_action_key
from app.connectors.action_catalog.f1_write_slice import is_f1_write_action
from app.connectors.action_catalog.models import ActionSpec
from app.connectors.action_catalog.registry import get_action_spec
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.read_preflight import (
    ParameterProvenance,
    PreflightResult,
    _blocked,
    _pick_from_source,
    _repair_class,
    _validate_constraints,
    apply_preflight_to_params,
    business_identity_from_context,
    seal_preflight_proof,
    strip_untrusted_preflight_markers,
    verify_bound_preflight,
)
from app.services.canonical_time_resolver import TimeWindow, resolve_time_window, time_window_from_mapping
from app.services.connector_resource_resolver import resolve_resource
from app.services.parameter_ledger import get_ledger, ingest_message_slots
from app.services.tool_types import ToolContext, ToolValidationError

logger = get_logger(__name__)


def _ledger_into_task_state(task_state: dict[str, Any], user_message: str) -> dict[str, Any]:
    merged = dict(task_state or {})
    ledger = ingest_message_slots(user_message, ledger=get_ledger(merged))
    for key, slot in ledger.slots.items():
        if slot.value and key not in merged:
            merged[key] = slot.value
        elif slot.value and key in {"to", "email", "subject", "body", "channel", "text", "message", "firstname", "lastname"}:
            merged[key] = slot.value
    if not merged.get("text") and merged.get("quoted"):
        merged["text"] = merged["quoted"]
    if not merged.get("body") and merged.get("quoted") and not merged.get("subject"):
        merged["body"] = merged["quoted"]
    merged["parameter_ledger"] = ledger.to_dict()
    return merged


def _prefer_ledger_over_model(proposed: dict[str, Any], task_state: dict[str, Any]) -> dict[str, Any]:
    out = dict(proposed)
    for key in ("to", "email", "subject", "body", "channel", "text", "message", "firstname", "lastname"):
        value = task_state.get(key)
        if value not in (None, ""):
            out[key] = value
    return out


def _finalize_hubspot_contact_properties(compiled: dict[str, Any]) -> dict[str, Any]:
    props = compiled.get("properties")
    if not isinstance(props, dict):
        props = {}
    else:
        props = dict(props)
    for key in ("email", "firstname", "lastname"):
        value = compiled.get(key)
        if value not in (None, "") and not props.get(key):
            props[key] = value
    if props:
        compiled["properties"] = props
    return compiled


def preflight_write_action(
    *,
    action_spec: ActionSpec | None = None,
    context: dict[str, Any] | None = None,
) -> PreflightResult:
    """Compile a bounded WRITE ActionSpec. Never invokes the provider. Never approves."""
    import time

    started = time.perf_counter()
    ctx = dict(context or {})
    proposed = strip_untrusted_preflight_markers(safe_normalize_stored_dict(ctx.get("proposed_args")))
    user_message = str(ctx.get("user_message") or ctx.get("message") or "")
    org_id = str(ctx.get("org_id") or "")
    client = ctx.get("client")
    settings = ctx.get("settings")
    task_state = _ledger_into_task_state(
        ctx.get("task_state") if isinstance(ctx.get("task_state"), dict) else {},
        user_message,
    )
    proposed = _prefer_ledger_over_model(proposed, task_state)
    connector_row = ctx.get("connector_row") if isinstance(ctx.get("connector_row"), dict) else None
    action_key = str(ctx.get("action_key") or "")
    plan_id = str(ctx.get("plan_id") or "").strip() or None
    step_id = str(ctx.get("step_id") or "").strip() or None
    capability_id = str(ctx.get("capability_id") or "") or None

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

    spec = action_spec or get_action_spec(catalog_action_key(action_key)) or get_action_spec(action_key)
    if spec is None or not is_f1_write_action(spec.id):
        return _blocked(
            error_class="ACTION_UNAVAILABLE",
            reason="action_not_in_f1_write_slice",
            repair_hint="use_catalog_write_key",
            started=started,
            result=result,
        )
    if spec.kind == "read":
        return _blocked(
            error_class="PERMISSION_BLOCKED",
            reason="read_not_in_f1_write_preflight",
            repair_hint="use_read_preflight",
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

    resource_type = spec.resource_requirements[0] if spec.resource_requirements else None
    conversation_context = {
        **task_state,
        "business_identity": identity,
        "org_id": org_id,
    }
    resolution = None
    if client is not None and settings is not None and org_id and resource_type:
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
    provenance = []
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

    if spec.id == "hubspot.contacts.create":
        compiled = _finalize_hubspot_contact_properties(compiled)
    if spec.id == "slack.post_message" and compiled.get("text") and not compiled.get("message"):
        compiled["message"] = compiled["text"]

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
    result.status = "ready"
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    seal_preflight_proof(result)
    logger.info(
        "f1_write_preflight_ok action=%s org=%s duration_ms=%s approval_not_granted=true",
        spec.id,
        org_id,
        result.duration_ms,
    )
    return result


def enforce_invoke_write_preflight(ctx: ToolContext, action: str, params: dict[str, Any]) -> dict[str, Any]:
    params = strip_untrusted_preflight_markers(params)
    if not is_f1_write_action(action):
        return params
    try:
        proof = verify_bound_preflight(ctx, action, params)
    except ToolValidationError as exc:
        if getattr(exc, "code", "") == "PREFLIGHT_REQUIRED":
            raise ToolValidationError(
                "That write wasn't compiled before execution.",
                code="PREFLIGHT_REQUIRED",
            ) from exc
        raise
    return apply_preflight_to_params(params, proof)


def compile_write_for_context(
    *,
    ctx: ToolContext,
    invoke_action: str,
    args: dict[str, Any] | None,
    user_message: str = "",
    connected_integrations: list[str] | None = None,
    task_state: dict[str, Any] | None = None,
) -> PreflightResult:
    return preflight_write_action(
        context={
            "action_key": catalog_action_key(invoke_action),
            "org_id": ctx.org_id,
            "client": ctx.client,
            "settings": ctx.settings,
            "proposed_args": dict(args or {}),
            "user_message": user_message,
            "environment_name": ctx.environment_name,
            "connected_integrations": list(connected_integrations or []),
            "task_state": dict(task_state or {}),
            "turn_id": getattr(ctx, "turn_id", None) or getattr(ctx, "conversation_id", None),
            "plan_id": getattr(ctx, "plan_id", None),
            "step_id": getattr(ctx, "step_id", None),
        }
    )
