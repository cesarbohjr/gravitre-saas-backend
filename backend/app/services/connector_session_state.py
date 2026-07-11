"""Structured Cowork-style connector session state for planning and inference."""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan

STEP_REF = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")

CONFIDENCE_BY_SOURCE: dict[str, str] = {
    "your last message": "high",
    "recent conversation": "medium",
    "only open project in asana": "medium",
    "session entity cache": "medium",
    "org entity cache": "medium",
    "orchestration step output": "high",
}

COMMON_BIND_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("email", ("email", "contact_email", "primary_email")),
    ("contact_id", ("contact_id", "id", "vid", "person_id")),
    ("company_id", ("company_id", "organization_id", "account_id")),
    ("name", ("name", "full_name", "display_name", "title")),
    ("list_id", ("list_id", "label_id", "listId")),
)


@dataclass
class ConnectorSessionState:
    """Working memory passed into planner/inference alongside raw messages."""

    active_entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    step_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_approval: dict[str, Any] | None = None
    session_summary: str = ""
    resolved_entities: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "activeEntities": deepcopy(self.active_entities),
            "stepOutputs": deepcopy(self.step_outputs),
            "pendingApproval": deepcopy(self.pending_approval),
            "sessionSummary": self.session_summary,
            "resolvedEntities": deepcopy(self.resolved_entities),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> ConnectorSessionState:
        if not isinstance(payload, dict):
            return cls()
        return cls(
            active_entities={
                str(key): dict(value)
                for key, value in (payload.get("activeEntities") or {}).items()
                if isinstance(value, dict)
            },
            step_outputs={
                str(key): dict(value)
                for key, value in (payload.get("stepOutputs") or {}).items()
                if isinstance(value, dict)
            },
            pending_approval=(
                dict(payload["pendingApproval"])
                if isinstance(payload.get("pendingApproval"), dict)
                else None
            ),
            session_summary=str(payload.get("sessionSummary") or ""),
            resolved_entities={
                str(key): str(value)
                for key, value in (payload.get("resolvedEntities") or {}).items()
                if str(value).strip()
            },
        )


def load_connector_session(task_state: dict[str, Any] | None) -> ConnectorSessionState:
    raw = (task_state or {}).get("connector_session")
    session = ConnectorSessionState.from_dict(raw if isinstance(raw, dict) else None)
    legacy = (task_state or {}).get("resolved_entities")
    if isinstance(legacy, dict):
        merged = dict(session.resolved_entities)
        for key, value in legacy.items():
            if str(value).strip():
                merged[str(key)] = str(value).strip()
        session = replace(session, resolved_entities=merged)
    legacy_outputs = _legacy_step_outputs(task_state)
    if legacy_outputs and not session.step_outputs:
        session = replace(session, step_outputs=legacy_outputs)
    return session


def connector_session_patch(session: ConnectorSessionState) -> dict[str, Any]:
    return {"connector_session": session.to_dict()}


def inference_confidence_for_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized.startswith("output of step_"):
        return "high"
    if normalized in CONFIDENCE_BY_SOURCE:
        return CONFIDENCE_BY_SOURCE[normalized]
    if normalized.startswith("session entity"):
        return "medium"
    return "medium"


def compress_session_for_context(
    session: ConnectorSessionState,
    *,
    max_entities: int = 8,
    max_steps: int = 6,
) -> dict[str, Any]:
    """Compact structured state for planner/inference prompts."""
    entities = list(session.active_entities.items())[-max_entities:]
    steps = list(session.step_outputs.items())[-max_steps:]
    return {
        "summary": session.session_summary,
        "entities": {key: value for key, value in entities},
        "stepOutputs": {key: value for key, value in steps},
        "resolvedEntities": dict(session.resolved_entities),
        "pendingApproval": session.pending_approval,
    }


def build_session_summary(
    *,
    completed_steps: list[dict[str, Any]] | None = None,
    step_outputs: dict[str, dict[str, Any]] | None = None,
    active_entities: dict[str, dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = []
    for row in (completed_steps or [])[-5:]:
        label = str(row.get("label") or row.get("step_id") or "Step").strip()
        url = str(row.get("url") or "").strip()
        if url:
            lines.append(f"- Completed: {label} ({url})")
        else:
            lines.append(f"- Completed: {label}")
    for key, payload in list((step_outputs or {}).items())[-3:]:
        summary = str(payload.get("summary") or payload.get("label") or key).strip()
        if summary:
            lines.append(f"- Step {key}: {summary[:160]}")
    for key, payload in list((active_entities or {}).items())[-4:]:
        label = str(payload.get("label") or key).strip()
        lines.append(f"- Entity {label}")
    return "\n".join(lines)


def record_step_output(
    session: ConnectorSessionState,
    *,
    step_id: str,
    invoke_action: str,
    label: str,
    success: bool,
    summary: str = "",
    url: str | None = None,
    structured: dict[str, Any] | None = None,
) -> ConnectorSessionState:
    outputs = dict(session.step_outputs)
    outputs[step_id] = {
        "stepId": step_id,
        "invokeAction": invoke_action,
        "label": label,
        "success": success,
        "summary": summary,
        "url": url,
        "structured": dict(structured or {}),
    }
    return replace(session, step_outputs=outputs)


def record_entity_from_execution(
    session: ConnectorSessionState,
    *,
    integration: str,
    invoke_action: str,
    entity_id: str | None,
    structured: dict[str, Any] | None,
    label: str,
    client: Any | None = None,
    org_id: str | None = None,
    conversation_id: str | None = None,
) -> ConnectorSessionState:
    entities = dict(session.active_entities)
    resource = invoke_action.split(".")[-2] if invoke_action.count(".") >= 2 else "entity"
    key = f"{integration}_{resource}"
    attributes = _extract_entity_attributes(structured or {})
    entities[key] = {
        "integration": integration,
        "invokeAction": invoke_action,
        "label": label,
        "entityId": entity_id,
        "attributes": attributes,
        "source": "orchestration step output",
        "confidence": "high",
    }
    resolved = dict(session.resolved_entities)
    if attributes.get("name"):
        resolved[f"{integration}_name"] = str(attributes["name"])
    if attributes.get("email"):
        resolved[f"{integration}_email"] = str(attributes["email"])
    updated = replace(session, active_entities=entities, resolved_entities=resolved)

    # Wave 5 — promote session bindings into durable org resolution store.
    if client and org_id:
        try:
            from app.services.entity_resolution_store import promote_from_session

            promote_from_session(
                client,
                org_id=org_id,
                session=updated,
                integration=integration,
                entity_id=entity_id,
                structured={**attributes, **(structured or {})},
                conversation_id=conversation_id,
                source="tool_output",
                confidence=0.85,
            )
        except Exception:  # noqa: BLE001
            pass
    return updated


def bind_plan_from_session(
    plan: ConnectorActionPlan,
    session: ConnectorSessionState,
    *,
    org_bindings: dict[str, tuple[str, str]] | None = None,
) -> ConnectorActionPlan:
    """Bind missing plan args from prior step outputs, session entities, and org cache."""
    args = dict(plan.args or {})
    inferred = list(plan.inferred_fields)
    sources = dict(plan.inference_sources)

    for arg_key, candidates in COMMON_BIND_KEYS:
        if _arg_present(args, arg_key):
            continue
        value, source = _lookup_binding(session, candidates, org_bindings=org_bindings, arg_key=arg_key)
        if value is None or not source:
            continue
        args[arg_key] = value
        inferred.append(arg_key)
        sources[arg_key] = source

    args = _interpolate_template_args(args, session)
    if not inferred and args == dict(plan.args or {}):
        return plan
    return replace(
        plan,
        args=args,
        inferred_fields=tuple(dict.fromkeys([*plan.inferred_fields, *inferred])),
        inference_sources=sources,
    )


def sync_legacy_resolved_entities(session: ConnectorSessionState) -> dict[str, str]:
    return dict(session.resolved_entities)


def _legacy_step_outputs(task_state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    params = (task_state or {}).get("clarified_params") or {}
    if not isinstance(params, dict):
        return {}
    outputs: dict[str, dict[str, Any]] = {}
    for row in params.get("step_results") or []:
        if not isinstance(row, dict):
            continue
        step_id = str(row.get("step_id") or row.get("stepId") or "").strip()
        if not step_id:
            continue
        outputs[step_id] = {
            "stepId": step_id,
            "invokeAction": row.get("invoke_action") or row.get("invokeAction") or "",
            "label": row.get("label") or "",
            "success": bool(row.get("success")),
            "summary": row.get("summary") or "",
            "url": row.get("url"),
            "structured": dict(row.get("structured") or {}),
        }
    return outputs


def _extract_entity_attributes(structured: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key, aliases in COMMON_BIND_KEYS:
        for alias in aliases:
            if alias in structured and structured[alias]:
                attrs[key] = structured[alias]
                break
    if structured.get("properties") and isinstance(structured["properties"], dict):
        for key, value in structured["properties"].items():
            if value:
                attrs[str(key)] = value
    return attrs


def _lookup_binding(
    session: ConnectorSessionState,
    candidates: tuple[str, ...],
    *,
    org_bindings: dict[str, tuple[str, str]] | None = None,
    arg_key: str | None = None,
) -> tuple[str | None, str | None]:
    for _step_id, payload in reversed(list(session.step_outputs.items())):
        structured = payload.get("structured")
        if isinstance(structured, dict):
            for candidate in candidates:
                value = structured.get(candidate)
                if value not in (None, ""):
                    step_id = str(payload.get("stepId") or _step_id)
                    return str(value), f"output of {step_id}"
    for entity in reversed(list(session.active_entities.values())):
        attributes = entity.get("attributes")
        if not isinstance(attributes, dict):
            continue
        for candidate in candidates:
            value = attributes.get(candidate)
            if value not in (None, ""):
                return str(value), "session entity cache"
    for candidate in candidates:
        legacy = session.resolved_entities.get(candidate)
        if legacy:
            return legacy, "session entity cache"
    # Wave 5 — org-level durable resolutions (after session miss).
    if org_bindings and arg_key and arg_key in org_bindings:
        value, source = org_bindings[arg_key]
        if value not in (None, ""):
            return str(value), source or "org entity cache"
    return None, None


def _interpolate_template_args(
    args: dict[str, Any],
    session: ConnectorSessionState,
) -> dict[str, Any]:
    updated = dict(args)
    for key, raw in list(updated.items()):
        if not isinstance(raw, str):
            continue

        def _replace(match: re.Match[str]) -> str:
            ref = match.group(1)
            if "." in ref:
                step_id, field = ref.split(".", 1)
                payload = session.step_outputs.get(step_id) or {}
                structured = payload.get("structured") if isinstance(payload.get("structured"), dict) else {}
                value = structured.get(field)
                return str(value) if value not in (None, "") else match.group(0)
            payload = session.step_outputs.get(ref) or session.active_entities.get(ref) or {}
            if isinstance(payload, dict):
                structured = payload.get("structured") if isinstance(payload.get("structured"), dict) else payload
                for candidate in ("email", "contact_id", "id", "name", "list_id"):
                    value = structured.get(candidate)
                    if value not in (None, ""):
                        return str(value)
            return match.group(0)

        updated[key] = STEP_REF.sub(_replace, raw)
    return updated


def _arg_present(args: dict[str, Any], key: str) -> bool:
    return bool(str(args.get(key) or "").strip())
