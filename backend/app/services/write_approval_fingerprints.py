"""Approved write target fingerprints (Release 2 argument sealing)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.canvas_write_gate import EXTERNAL_WRITE_STEP_TYPES, _invoke_action_from_step, _iter_definition_steps
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.tool_service import STEP_TYPE_TO_ACTION

# Fields that define *who/what* a write targets — not free-form body content.
_TARGET_ARG_KEYS = frozenset(
    {
        "to",
        "email",
        "channel",
        "channel_id",
        "recipient",
        "recipients",
        "record_id",
        "id",
        "entity_id",
        "contact_id",
        "deal_id",
        "ticket_id",
        "list_id",
        "account_id",
        "company_id",
        "phone",
        "user_id",
    }
)


def _normalize_target_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    out: dict[str, Any] = {}
    for key in sorted(_TARGET_ARG_KEYS):
        if key not in data or data[key] in (None, "", [], {}):
            continue
        val = data[key]
        if isinstance(val, list):
            out[key] = sorted(str(x).strip().lower() for x in val)
        else:
            out[key] = str(val).strip().lower()
    return out


def write_target_fingerprint(*, invoke_action: str, payload: dict[str, Any] | None) -> str:
    body = {
        "invoke_action": str(invoke_action or "").strip(),
        "targets": _normalize_target_payload(payload),
    }
    raw = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def allowed_write_targets_from_definition(definition: dict[str, Any] | None) -> list[dict[str, str]]:
    """Target fingerprints sealed from the reviewed workflow definition."""
    out: list[dict[str, str]] = []
    for step in _iter_definition_steps(definition):
        stype = str(step.get("type") or "").strip()
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        action: str | None = None
        if stype in EXTERNAL_WRITE_STEP_TYPES:
            action = STEP_TYPE_TO_ACTION.get(stype)
        elif stype == "invoke_tool":
            action = str(cfg.get("action") or cfg.get("tool_action") or "").strip() or None
        if not action or not invoke_action_requires_write_approval(action):
            continue
        fp = write_target_fingerprint(invoke_action=action, payload=cfg)
        out.append({"invoke_action": action, "fingerprint": fp})
    # Stable order for storage
    return sorted(out, key=lambda x: (x["invoke_action"], x["fingerprint"]))


def invoke_target_allowed(
    *,
    invoke_action: str,
    params: dict[str, Any] | None,
    allowed_targets: list[dict[str, str]] | None,
) -> bool:
    if not allowed_targets:
        return True
    fp = write_target_fingerprint(invoke_action=invoke_action, payload=params)
    for row in allowed_targets:
        if row.get("invoke_action") == invoke_action and row.get("fingerprint") == fp:
            return True
    return False
