"""Read-only compiled_task projection on conversation task_state (audit §34 item 4).

Assembled from Phase A resolution + E5 ExecutionPlan (+ optional F1 preflight).
Not a new runtime. Dispatchers must not mutate this blob independently — persist
reprojects it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.canonical_time_resolver import resolve_time_window
from app.services.org_business_identity import merge_business_identity

_SECRET_PARTS = ("token", "secret", "password", "authorization", "api_key")


def _safe_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    return {
        key: value
        for key, value in params.items()
        if not any(part in str(key).lower() for part in _SECRET_PARTS)
    }


def _preflight_dict(preflight: Any) -> dict[str, Any]:
    if preflight is None:
        return {}
    if isinstance(preflight, dict):
        return preflight
    as_dict = getattr(preflight, "as_dict", None)
    if callable(as_dict):
        payload = as_dict()
        return payload if isinstance(payload, dict) else {}
    return {
        "status": getattr(preflight, "status", None),
        "action_key": getattr(preflight, "action_key", None),
        "connector_id": getattr(preflight, "connector_id", None),
        "compiled_parameters": getattr(preflight, "compiled_parameters", None),
        "time_window": getattr(preflight, "time_window", None),
        "capability_id": getattr(preflight, "capability_id", None),
        "resource": getattr(preflight, "resource", None),
        "error_class": getattr(preflight, "error_class", None),
    }


@dataclass(frozen=True)
class CompiledTask:
    objective_text: str = ""
    capability_id: str | None = None
    timeframe_resolved: dict[str, str] | None = None
    sources: tuple[dict[str, Any], ...] = ()
    action_keys: tuple[str, ...] = ()
    compiled_parameters: dict[str, Any] = field(default_factory=dict)
    clarification_decision: dict[str, Any] | None = None
    preflight_status: str | None = None
    turn_id: str | None = None
    org_id: str | None = None
    plan_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective_text": self.objective_text,
            "capability_id": self.capability_id,
            "timeframe_resolved": dict(self.timeframe_resolved) if self.timeframe_resolved else None,
            "sources": [dict(row) for row in self.sources],
            "action_keys": list(self.action_keys),
            "compiled_parameters": dict(self.compiled_parameters),
            "clarification_decision": dict(self.clarification_decision)
            if isinstance(self.clarification_decision, dict)
            else None,
            "preflight_status": self.preflight_status,
            "turn_id": self.turn_id,
            "org_id": self.org_id,
            "plan_id": self.plan_id,
        }


def project_compiled_task(
    task_state: dict[str, Any] | None,
    *,
    objective_text: str | None = None,
    capability_id: str | None = None,
    preflight: Any = None,
    resolution: Any = None,
    org_id: str | None = None,
) -> CompiledTask:
    state = task_state if isinstance(task_state, dict) else {}
    proof = _preflight_dict(preflight) or (
        state.get("last_read_preflight") if isinstance(state.get("last_read_preflight"), dict) else {}
    )

    objective = str(
        objective_text
        or state.get("cognitive_resolution_message")
        or (state.get("execution_plan") or {}).get("summary")
        or (state.get("execution_plan") or {}).get("objective")
        or ""
    ).strip()

    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    trace = state.get("resolution_trace") if isinstance(state.get("resolution_trace"), dict) else {}
    analysis = state.get("active_analysis") if isinstance(state.get("active_analysis"), dict) else {}

    cap = (
        capability_id
        or proof.get("capability_id")
        or plan.get("capability_id")
        or analysis.get("kind")
        or None
    )
    cap = str(cap).strip() or None

    identity = merge_business_identity(
        org_id=str(org_id or trace.get("tenant_id") or ""),
        context=state,
        user_message=objective,
        client=None,
    )
    window = proof.get("time_window") if isinstance(proof.get("time_window"), dict) else None
    if window is None and objective:
        resolved = resolve_time_window(objective, timezone_name=identity.get("timezone"))
        window = resolved.as_dict() if resolved else None

    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add_source(connector: str | None, resource_id: str | None, display_name: str | None = None) -> None:
        cid = str(connector or "").strip()
        rid = str(resource_id or "").strip()
        if not cid and not rid:
            return
        key = (cid, rid)
        if key in seen:
            return
        seen.add(key)
        sources.append(
            {
                "connector": cid or None,
                "resource_id": rid or None,
                "display_name": str(display_name or rid or cid),
            }
        )

    resource = getattr(resolution, "resource", None)
    if resource is not None and getattr(resource, "status", None) == "resolved":
        _add_source(resource.connector_id, resource.resource_id, resource.display_name)
    proof_resource = proof.get("resource") if isinstance(proof.get("resource"), dict) else {}
    if proof_resource:
        _add_source(
            proof.get("connector_id"),
            proof_resource.get("id") or proof_resource.get("resource_id"),
            proof_resource.get("name") or proof_resource.get("display_name"),
        )
    _add_source(trace.get("resolved_connector_id"), trace.get("resource_id"))
    _add_source(analysis.get("connector_id"), analysis.get("property_id"), analysis.get("property_name"))
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        _add_source(
            step.get("connector_id"),
            meta.get("property_id") or meta.get("site_url") or meta.get("resource_id"),
            step.get("title"),
        )

    action_keys: list[str] = []
    for key in (
        proof.get("action_key"),
        *(str(s.get("action_key") or "") for s in (plan.get("steps") or []) if isinstance(s, dict)),
    ):
        text = str(key or "").strip()
        if text and text not in action_keys:
            action_keys.append(text)

    params = _safe_params(proof.get("compiled_parameters"))
    if not params:
        for step in plan.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("meta"), dict):
                args = step["meta"].get("args")
                if isinstance(args, dict) and args:
                    params = _safe_params(args)
                    break

    clarification = None
    if resolution is not None and getattr(resolution, "clarification", None) is not None:
        decision = resolution.clarification
        clarification = {
            "required": bool(getattr(decision, "should_ask", False)),
            "reason": str(getattr(decision, "reason", None) or ""),
        }
    elif trace.get("clarification_required") is not None:
        clarification = {
            "required": bool(trace.get("clarification_required")),
            "reason": str(trace.get("resolution_reason") or ""),
        }

    preflight_status = str(proof.get("status") or "").strip() or None
    turn_id = str(
        proof.get("turn_id")
        or trace.get("turn_id")
        or plan.get("turn_id")
        or (state.get("cognitive_turn_trace") or {}).get("turn_id")
        or ""
    ).strip() or None

    return CompiledTask(
        objective_text=objective,
        capability_id=cap,
        timeframe_resolved=window,
        sources=tuple(sources),
        action_keys=tuple(action_keys),
        compiled_parameters=params,
        clarification_decision=clarification,
        preflight_status=preflight_status,
        turn_id=turn_id,
        org_id=str(org_id or trace.get("tenant_id") or "").strip() or None,
        plan_id=str(plan.get("plan_id") or "").strip() or None,
    )


def attach_compiled_task(
    task_state: dict[str, Any] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    state = dict(task_state) if isinstance(task_state, dict) else {}
    projected = project_compiled_task(state, **kwargs)
    state["compiled_task"] = projected.as_dict()
    try:
        from app.services.business_entity_fabric import website_entity_from_identity
        from app.services.org_business_identity import merge_business_identity

        identity = merge_business_identity(
            org_id=str(kwargs.get("org_id") or projected.org_id or ""),
            context=state,
            user_message=projected.objective_text,
            client=None,
        )
        params = projected.compiled_parameters if isinstance(projected.compiled_parameters, dict) else {}
        entity = website_entity_from_identity(
            org_id=str(projected.org_id or kwargs.get("org_id") or ""),
            identity=identity,
            ga4_property_id=str(params.get("property_id") or "") or None,
            gsc_site_url=str(params.get("site_url") or "") or None,
        )
        if entity is not None:
            state["business_entity"] = entity.as_dict()
    except Exception:  # noqa: BLE001
        pass
    return state


def attach_compiled_task_to_patch(
    patch: dict[str, Any],
    *,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = {**(current_state if isinstance(current_state, dict) else {}), **dict(patch)}
    projected = project_compiled_task(merged)
    out = dict(patch)
    out["compiled_task"] = projected.as_dict()
    return out


_PROMPT_PARAM_KEYS = ("start_date", "end_date", "site_url")


def _payload_from_task_state(task_state: dict[str, Any] | None) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    raw = state.get("compiled_task")
    if isinstance(raw, dict) and (
        raw.get("capability_id")
        or raw.get("sources")
        or raw.get("timeframe_resolved")
        or raw.get("preflight_status")
        or (isinstance(raw.get("clarification_decision"), dict) and raw["clarification_decision"].get("required"))
    ):
        return raw
    return project_compiled_task(state).as_dict()


def format_compiled_task_compiler_block(task_state: dict[str, Any] | None) -> str:
    """E4 slice: resolved business task, not tool names or API ids."""
    payload = _payload_from_task_state(task_state)
    capability = str(payload.get("capability_id") or "").strip()
    timeframe = payload.get("timeframe_resolved") if isinstance(payload.get("timeframe_resolved"), dict) else {}
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    clarification = (
        payload.get("clarification_decision")
        if isinstance(payload.get("clarification_decision"), dict)
        else {}
    )
    preflight = str(payload.get("preflight_status") or "").strip()
    params = payload.get("compiled_parameters") if isinstance(payload.get("compiled_parameters"), dict) else {}
    if not (capability or sources or timeframe or preflight or clarification.get("required")):
        return ""

    lines = [
        "COMPILED TASK (authoritative for this turn — already resolved; do not re-ask these):",
    ]
    if capability:
        lines.append(f"capability={capability}")
    interp = str(timeframe.get("interpretation") or "").strip()
    start = str(timeframe.get("start_iso") or params.get("start_date") or "").strip()
    end = str(timeframe.get("end_iso") or params.get("end_date") or "").strip()
    if interp or (start and end):
        window = interp or "resolved_window"
        if start and end:
            lines.append(f"timeframe={window} {start} to {end}")
        else:
            lines.append(f"timeframe={window}")
    for row in sources:
        if not isinstance(row, dict):
            continue
        connector = str(row.get("connector") or "").strip()
        name = str(row.get("display_name") or "").strip()
        resource_id = str(row.get("resource_id") or "").strip()
        label = name
        if not label or label == resource_id:
            label = connector or "connected source"
        if connector:
            lines.append(f"source={connector} ({label})")
        elif label:
            lines.append(f"source={label}")
    if clarification.get("required"):
        lines.append("clarification=required — ask only among the remaining valid business options")
    else:
        lines.append("clarification=not_required")
    if preflight:
        lines.append(f"readiness={preflight}")
    for key in _PROMPT_PARAM_KEYS:
        value = params.get(key)
        if value in (None, ""):
            continue
        if key == "site_url":
            from app.services.org_business_identity import normalize_host

            host = normalize_host(str(value))
            if host:
                lines.append(f"website={host}")
            continue
        lines.append(f"{key}={value}")
    body = "\n".join(lines)
    try:
        from app.services.agent_security_gateway import fence_page_context_block

        return fence_page_context_block(body)
    except Exception:  # noqa: BLE001
        return body
