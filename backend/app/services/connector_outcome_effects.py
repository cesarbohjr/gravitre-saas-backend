"""Classify connector write effects so no-op / idempotent finds are not sold as creates.

Class-level guard for false COMPLETED claims (e.g. Apollo label already exists →
"Found existing MSP Prospects" marked created_record + completed with 0 steps).

Vendor-wide OutcomeEffect gate: mutating actions without entity proof (or with
idempotent/async/noop markers) must not terminal as COMPLETED.
"""
from __future__ import annotations

import re
from typing import Any, Literal

OutcomeEffect = Literal[
    "created",
    "updated",
    "already_existed",
    "accepted_async",
    "noop",
    "unknown",
    "read",
]

MUTATING_ACTION_MARKERS = (
    ".create",
    ".update",
    ".add",
    ".delete",
    ".send",
    ".enroll",
    ".push",
    ".sync",
    ".request",
    ".post",
    ".write",
    ".pause",
    ".resume",
)

_NOOP_MARKERS = (
    "noop",
    "no_op",
    "no-op",
    "skipped",
    "unchanged",
    "not_modified",
)

# Multi-vendor enrich/sync language that must not collapse to single-list create.
_ENRICH_OR_SYNC = re.compile(
    r"\b("
    r"enrich(?:ment|ed|ing)?"
    r"|clay"
    r"|sync(?:ed|ing)?"
    r"|then\s+add"
    r"|add\s+those"
    r"|static\s+list"
    r"|hubspot\s+(?:static\s+)?list"
    r")\b",
    re.IGNORECASE,
)


def is_already_existed_effect(result_data: dict[str, Any] | None) -> bool:
    """True when vendor returned an idempotent find (no net-new create)."""
    if not isinstance(result_data, dict):
        return False
    if result_data.get("already_existed") is True:
        return True
    if str(result_data.get("outcome_effect") or "").strip().lower() == "already_existed":
        return True
    nested = result_data.get("label") if isinstance(result_data.get("label"), dict) else None
    if isinstance(nested, dict) and nested.get("already_existed") is True:
        return True
    return False


def is_mutating_action(invoke_action: str | None) -> bool:
    action = str(invoke_action or "").strip().lower()
    if not action:
        return False
    return any(marker in action for marker in MUTATING_ACTION_MARKERS)


def _truthy_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_vendor_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return True
    return False


_INTERNAL_ENTITY_TYPES = frozenset(
    {"connector", "workflow_run", "execution", "agent", "agent_job", "operator"}
)


def has_effect_proof(result_data: dict[str, Any] | None, verified_output: Any = None) -> bool:
    """True if an entity id / list id / contact id / vendor URL is present."""
    bags: list[dict[str, Any]] = []
    if isinstance(result_data, dict):
        bags.append(result_data)
        for nested_key in ("label", "data", "result", "record", "contact", "list"):
            nested = result_data.get(nested_key)
            if isinstance(nested, dict):
                bags.append(nested)
    if isinstance(verified_output, dict):
        bags.append(verified_output)
    elif verified_output is not None:
        bags.append(
            {
                "entity_id": getattr(verified_output, "entity_id", None),
                "entity_type": getattr(verified_output, "entity_type", None),
                "external_url": getattr(verified_output, "external_url", None),
                "result_url": getattr(verified_output, "result_url", None),
            }
        )

    # Vendor-native ids. entity_id counts only when not a Gravitre-internal type.
    id_keys = (
        "list_id",
        "contact_id",
        "id",
        "external_id",
        "record_id",
        "lead_id",
    )
    for bag in bags:
        for key in id_keys:
            if _truthy_str(bag.get(key)):
                return True
        entity_type = str(bag.get("entity_type") or "").strip().lower()
        if _truthy_str(bag.get("entity_id")) and entity_type not in _INTERNAL_ENTITY_TYPES:
            # Bare entity_id without an internal type still counts (vendor payload).
            if entity_type or bag.get("entity_id") != bag.get("connector_id"):
                return True
        external = _truthy_str(bag.get("external_url"))
        if _looks_like_vendor_url(external):
            return True
        result_url = _truthy_str(bag.get("result_url"))
        # Vendor http URLs count; in-app /runs/... alone is not create proof.
        if _looks_like_vendor_url(result_url):
            return True
    return False


def _has_async_markers(bag: dict[str, Any]) -> bool:
    effect = str(bag.get("outcome_effect") or "").strip().lower()
    if effect == "accepted_async":
        return True
    status = str(bag.get("status") or bag.get("job_status") or "").strip().lower()
    if status in {"accepted", "queued", "pending", "processing", "submitted", "async"}:
        return True
    if bag.get("accepted_async") is True:
        return True
    for key in ("job_id", "jobId", "batch_id", "batchId", "async_job_id"):
        if _truthy_str(bag.get(key)):
            return True
    raw = str(bag.get("message") or bag.get("detail") or "").lower()
    if "accepted" in raw and "async" in raw:
        return True
    return False


def _has_noop_markers(bag: dict[str, Any]) -> bool:
    effect = str(bag.get("outcome_effect") or "").strip().lower()
    if effect == "noop":
        return True
    if bag.get("noop") is True or bag.get("no_op") is True:
        return True
    status = str(bag.get("status") or "").strip().lower()
    if status in _NOOP_MARKERS:
        return True
    return False


def classify_write_effect(
    *,
    invoke_action: str | None,
    result_data: dict[str, Any] | None,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Classify the write effect of a connector/tool invocation.

    Priority:
      1. explicit metadata/result outcome_effect or already_existed → already_existed
      2. accepted_async / async job markers → accepted_async
      3. mutating + success but no entity proof → unknown
      4. mutating + proof → created (or updated if .update in action)
      5. non-mutating → read
      6. noop markers (checked after already_existed / async; before inventing created)
    """
    meta = metadata if isinstance(metadata, dict) else {}
    data = result_data if isinstance(result_data, dict) else {}
    merged: dict[str, Any] = {**meta, **data}

    # 1. Explicit already_existed / outcome_effect
    if is_already_existed_effect(merged) or is_already_existed_effect(data) or is_already_existed_effect(meta):
        return "already_existed"
    explicit = str(merged.get("outcome_effect") or meta.get("outcome_effect") or "").strip().lower()
    if explicit == "already_existed":
        return "already_existed"
    if explicit in {"accepted_async", "noop", "unknown", "read", "created", "updated"}:
        # Honor explicit classifications from callers/vendors.
        if explicit == "created" and not has_effect_proof(data, meta.get("verified_output")):
            # Soft: don't trust "created" without proof when mutating.
            if is_mutating_action(invoke_action) and success:
                return "unknown"
        return explicit
    if explicit == "write":
        # Legacy marker from chat_connector — reclassify with proof rules below.
        pass

    # 2. Async acceptance
    if _has_async_markers(merged) or _has_async_markers(data):
        return "accepted_async"

    # 6 (elevated): noop markers before inventing created/updated
    if _has_noop_markers(merged) or _has_noop_markers(data):
        return "noop"

    mutating = is_mutating_action(invoke_action)
    if not mutating:
        return "read"

    if not success:
        return "unknown"

    proven = has_effect_proof(data, meta.get("verified_output"))
    # 3. Mutating success without proof
    if not proven:
        return "unknown"

    # 4. Mutating with proof
    action = str(invoke_action or "").lower()
    if ".update" in action or ".modify" in action:
        return "updated"
    return "created"


def coerce_terminal_status_for_effect(
    *,
    status: str,
    effect: str,
    invoke_action: str | None,
) -> str:
    """Downgrade false COMPLETED when a mutating write lacks a proven create."""
    normalized = str(status or "").strip().lower()
    effect_norm = str(effect or "").strip().lower()
    if (
        normalized == "completed"
        and is_mutating_action(invoke_action)
        and effect_norm in {"already_existed", "noop", "accepted_async", "unknown"}
    ):
        return "partial_success"
    return status


def is_multi_system_enrich_or_sync_intent(message: str) -> bool:
    """True when NL asks for list work spanning ≥2 of Apollo/Clay/HubSpot with enrich/sync.

    Prevents LIST_CREATE_INTENT from suppressing orchestration for prompts like:
    Use Clay to enrich Apollo list \"MSP Prospects\", then add to HubSpot static list \"MSPs\".
    """
    text = (message or "").strip().lower()
    if not text:
        return False
    vendors = sum(1 for v in ("apollo", "clay", "hubspot") if v in text)
    if vendors < 2:
        return False
    return bool(_ENRICH_OR_SYNC.search(text))


def prefers_single_list_create(message: str) -> bool:
    """STA-305 omit-name list create prefers governed connector — unless multi-system enrich."""
    from app.services.chat_connector_models import LIST_CREATE_INTENT

    if not LIST_CREATE_INTENT.search(message or ""):
        return False
    if is_multi_system_enrich_or_sync_intent(message or ""):
        return False
    return True


def already_existed_list_summary(
    *,
    name: str | None,
    list_id: str | None,
) -> str:
    """Honest summary: found shell list, did not populate contacts or sync CRM."""
    label = f'"{name}"' if name else "contact list"
    id_part = f" (id: {list_id})" if list_id else ""
    return (
        f"Found existing contact list {label}{id_part}. "
        "No contacts were added and no HubSpot sync ran — "
        "this is an idempotent find, not a populate or enrich action."
    )
