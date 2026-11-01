"""Generic write-action completion summaries for verified output contract.

Used when a connector-specific mapper is not present. Extracts common id/name
fields from API payloads so every verified write returns a non-empty body.
``result_url`` remains optional — null is a valid final contract when the vendor
has no stable deep link.
"""
from __future__ import annotations

from typing import Any

_ID_KEYS = (
    "id",
    "gid",
    "key",
    "number",
    "uuid",
    "entity_id",
    "record_id",
    "object_id",
    "hs_object_id",
    "contact_id",
    "deal_id",
    "ticket_id",
    "issue_id",
    "task_id",
    "page_id",
    "file_id",
    "message_id",
    "customer_id",
    "invoice_id",
    "lead_id",
    "opportunity_id",
    "subscriber_id",
)

_NAME_KEYS = (
    "name",
    "title",
    "subject",
    "summary",
    "email",
    "label",
    "dealname",
    "fullname",
    "display_name",
    "full_name",
)

_NESTED_KEYS = (
    "contact",
    "deal",
    "issue",
    "ticket",
    "task",
    "page",
    "file",
    "message",
    "customer",
    "invoice",
    "lead",
    "opportunity",
    "record",
    "item",
    "data",
    "result",
    "label",
    "properties",
    "fields",
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_str(container: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = container.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _walk_payloads(result_data: dict[str, Any] | None, args: dict[str, Any] | None) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    data = _as_dict(result_data)
    if data:
        payloads.append(data)
        for nested_key in _NESTED_KEYS:
            nested = data.get(nested_key)
            if isinstance(nested, dict):
                payloads.append(nested)
                inner_props = nested.get("properties")
                if isinstance(inner_props, dict):
                    payloads.append(inner_props)
    if args:
        payloads.append(dict(args))
    return payloads


def extract_resource_id(
    result_data: dict[str, Any] | None,
    *,
    args: dict[str, Any] | None = None,
) -> str | None:
    for payload in _walk_payloads(result_data, args):
        found = _first_str(payload, _ID_KEYS)
        if found:
            return found
    return None


def extract_resource_label(
    result_data: dict[str, Any] | None,
    *,
    args: dict[str, Any] | None = None,
) -> str | None:
    for payload in _walk_payloads(result_data, args):
        first = str(payload.get("firstname") or payload.get("first_name") or "").strip()
        last = str(payload.get("lastname") or payload.get("last_name") or "").strip()
        full = " ".join(bit for bit in (first, last) if bit).strip()
        if full:
            return full
        found = _first_str(payload, _NAME_KEYS)
        if found:
            return found
    return None


def _humanize_action(action: str) -> tuple[str, str]:
    """Return (verb phrase, resource label) from vendor.resource.verb keys."""
    parts = [p for p in str(action or "").split(".") if p]
    if len(parts) >= 3:
        vendor, resource, verb = parts[0], parts[1], parts[-1]
    elif len(parts) == 2:
        vendor, resource, verb = parts[0], parts[1], "completed"
    else:
        return "Completed", action or "action"

    vendor_label = vendor.replace("_", " ").title()
    resource_label = resource.replace("_", " ").rstrip("s")
    if resource.endswith("s") and not resource.endswith("ss"):
        resource_label = resource[:-1].replace("_", " ")

    verb_l = verb.lower()
    if verb_l in {"create", "add", "insert", "put", "upload", "send", "post", "track", "trigger", "enable", "activate", "schedule", "submit", "publish"}:
        return f"Created {vendor_label}", resource_label
    if verb_l in {"update", "set", "append", "reply", "comment", "tag", "close", "resolve", "acknowledge", "merge"}:
        return f"Updated {vendor_label}", resource_label
    if verb_l in {"delete", "remove"}:
        return f"Deleted {vendor_label}", resource_label
    return f"Completed {vendor_label}", f"{resource_label} {verb_l}".strip()


def summarize_write_action(
    *,
    action: str,
    result_data: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
) -> str:
    """Non-empty completion line suitable for ExecutionResult.body."""
    if action == 'assistant.generate_image':
        import re
        payload = result_data if isinstance(result_data,dict) else {}
        if (payload.get('status') == 'ok' and payload.get('artifact_verified') is True
                and re.fullmatch(r'[a-f0-9]{64}',str(payload.get('sha256','')))
                and payload.get('storage_path') and payload.get('hostedFiles')):
            return 'Generated one private draft image and verified the stored file. It is available in the attached artifact.'
        return 'Image generation has no verified stored artifact; completion is unconfirmed.'
    from app.services.native_runtime.specs import DEFINITIONS as native_definitions
    if action.removeprefix('assistant.') in native_definitions and action.startswith('assistant.'):
        from uuid import UUID
        data=result_data if isinstance(result_data,dict) else {}
        job_id=str(data.get('job_id') or (args or {}).get('job_id') or '')
        try:job_id=str(UUID(job_id))
        except ValueError:job_id='unconfirmed'
        state=data.get('state')
        if state not in {'queued','running','completed','failed','cancelled','uncertain','expired','deleted','delivered','approved','denied'}:state='unconfirmed'
        if action=='assistant.export_evaluation_metrics':
            return f'Metrics job {job_id}: {state}. Delivery is confirmed only by the durable worker’s exact remote observation readback.'
        if action=='assistant.approve_native_action':
            return f'Browser action decision: {state}. Native job {job_id}; execution remains unverified.'
        return f'Native job {job_id}: {state}. Draft artifacts require review; external execution remains unverified.'
    verb_phrase, resource = _humanize_action(action)
    label = extract_resource_label(result_data, args=args)
    resource_id = extract_resource_id(result_data, args=args)

    subject = label or resource
    if label and resource and label.lower() != resource.lower():
        # e.g. Created HubSpot contact Ada (id: 1)
        subject = f"{resource} {label}"

    if resource_id:
        return f'{verb_phrase} {subject} (id: {resource_id}).'
    return f"{verb_phrase} {subject}."


def resolve_generic_result_url(result_data: dict[str, Any] | None) -> str | None:
    data = _as_dict(result_data)
    for key in ("url", "html_url", "link", "permalink", "web_url", "browseUrl"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    for nested_key in _NESTED_KEYS:
        nested = data.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in ("url", "html_url", "link", "permalink", "web_url", "browseUrl"):
            value = nested.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    return None
