"""Collect vendor/deep-link refs from workflow step output snapshots.

Used so Runs + BusinessOutcome can surface “open completed work in Apollo/HubSpot”
instead of only a generic /runs/{id} link.
"""
from __future__ import annotations

from typing import Any


_URL_KEYS = (
    "external_url",
    "result_url",
    "url",
    "html_url",
    "permalink",
    "web_url",
    "link",
)


def _first_http_url(*candidates: Any) -> str | None:
    for value in candidates:
        text = str(value or "").strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text
    return None


def _snapshot_of(step: dict[str, Any]) -> dict[str, Any]:
    raw = step.get("output_snapshot")
    if isinstance(raw, dict):
        return raw
    # Some callers flatten the snapshot onto the step row.
    return step if isinstance(step, dict) else {}


def extract_step_output_ref(step: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one step into a compact output ref for UI/evidence."""
    if not isinstance(step, dict):
        return None
    snap = _snapshot_of(step)
    nested = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    structured = snap.get("structured") if isinstance(snap.get("structured"), dict) else {}

    external = _first_http_url(
        snap.get("external_url"),
        *(snap.get(k) for k in _URL_KEYS),
        *(nested.get(k) for k in _URL_KEYS),
        *(structured.get(k) for k in _URL_KEYS),
        step.get("external_url"),
        step.get("result_url"),
    )
    gravitre_url = None
    for key in ("result_url", "url"):
        candidate = str(snap.get(key) or step.get(key) or "").strip()
        if candidate.startswith("/") and not candidate.startswith("//"):
            gravitre_url = candidate
            break

    invoke_action = str(
        snap.get("invoke_action")
        or snap.get("action")
        or step.get("invoke_action")
        or ""
    ).strip() or None
    integration = str(
        snap.get("integration")
        or (invoke_action.split(".", 1)[0] if invoke_action and "." in invoke_action else "")
        or step.get("integration")
        or ""
    ).strip() or None
    summary = str(
        snap.get("summary")
        or step.get("summary")
        or snap.get("message")
        or ""
    ).strip()[:500] or None
    entity_id = str(
        snap.get("entity_id")
        or snap.get("list_id")
        or snap.get("contact_id")
        or snap.get("id")
        or nested.get("list_id")
        or nested.get("contact_id")
        or nested.get("id")
        or ""
    ).strip() or None
    outcome_effect = str(snap.get("outcome_effect") or "").strip() or None
    already_existed = bool(snap.get("already_existed") is True)

    if not any((external, gravitre_url, entity_id, summary, invoke_action)):
        return None

    return {
        "label": str(step.get("step_name") or step.get("name") or step.get("label") or invoke_action or "Step"),
        "status": str(step.get("status") or ("completed" if snap.get("success") else "unknown")),
        "summary": summary,
        "invoke_action": invoke_action,
        "integration": integration,
        "external_url": external,
        "result_url": gravitre_url,
        "entity_id": entity_id,
        "outcome_effect": outcome_effect,
        "already_existed": already_existed,
        "success": bool(snap.get("success", str(step.get("status") or "").lower() in {"completed", "success"})),
    }


def collect_connector_output_refs(steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        ref = extract_step_output_ref(step)
        if ref:
            refs.append(ref)
    return refs


def primary_vendor_url(refs: list[dict[str, Any]]) -> str | None:
    for ref in refs:
        url = _first_http_url(ref.get("external_url"), ref.get("result_url"))
        if url:
            return url
    return None


def enrich_invoke_tool_snapshot(
    *,
    action: str,
    data: dict[str, Any],
    success: bool = True,
) -> dict[str, Any]:
    """Stamp outcome_effect + deep links onto invoke_tool step snapshots."""
    from app.services.connector_outcome_effects import classify_write_effect

    payload = dict(data or {})
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    external = _first_http_url(
        payload.get("external_url"),
        *(payload.get(k) for k in _URL_KEYS),
        *(nested.get(k) for k in _URL_KEYS),
    )
    if external and not payload.get("external_url"):
        payload["external_url"] = external
    payload["invoke_action"] = action
    if "." in action:
        payload.setdefault("integration", action.split(".", 1)[0])
    if not payload.get("summary"):
        for key in ("message", "body", "detail"):
            text = str(payload.get(key) or "").strip()
            if text:
                payload["summary"] = text[:2000]
                break
    effect = classify_write_effect(
        invoke_action=action,
        result_data=payload,
        success=success,
        metadata={"already_existed": bool(payload.get("already_existed"))},
    )
    payload["outcome_effect"] = effect
    if payload.get("already_existed") is True or effect == "already_existed":
        payload["already_existed"] = True
    payload["success"] = success
    return payload
