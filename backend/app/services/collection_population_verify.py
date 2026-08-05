"""F6 — follow-up vendor state checks for list populate / membership writes.

After apollo.lists.add / hubspot.lists.add_contact (and siblings), do not mark
the outcome fully created/verified until a follow-up read confirms membership
count > 0 (or the write payload itself carries membership proof). Async /
rate-limited follow-up → accepted_async / partial per effect honesty.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.list_populate_honesty import (
    LIST_ADD_ACTIONS,
    has_list_membership_proof,
    is_list_add_action,
    membership_contact_count,
)

logger = logging.getLogger(__name__)

POPULATION_ACTIONS = frozenset(
    {
        *LIST_ADD_ACTIONS,
        "apollo.lists.add",
        "hubspot.lists.add_contact",
        "marketo.lists.add_to_static_list",
    }
)


@dataclass(frozen=True)
class PopulationVerifyResult:
    verified: bool
    effect: str  # created | accepted_async | unknown | partial
    membership_count: int
    detail: str
    follow_up_attempted: bool = False


def is_population_write_action(action: str | None) -> bool:
    return str(action or "").strip().lower() in POPULATION_ACTIONS


def verify_collection_population(
    *,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    client: Any = None,
    org_id: str | None = None,
    settings: Any = None,
    environment_name: str = "production",
    ctx: Any = None,
) -> PopulationVerifyResult:
    """Confirm real list membership after a populate/sync write.

    Order:
      1. Membership proof already present in the write response → verified/created
      2. Follow-up vendor read (when wired) → count > 0
      3. Else unknown / accepted_async — never bare created
    """
    action = str(invoke_action or "").strip().lower()
    data = result_data if isinstance(result_data, dict) else {}
    if not is_population_write_action(action):
        return PopulationVerifyResult(
            verified=True,
            effect="created",
            membership_count=0,
            detail="not_a_population_action",
        )

    proof_ref = {
        "invoke_action": action,
        "success": True,
        **data,
    }
    inline_count = membership_contact_count(data)
    if has_list_membership_proof(proof_ref) or inline_count > 0:
        return PopulationVerifyResult(
            verified=True,
            effect="created",
            membership_count=max(inline_count, 1),
            detail="write_response_membership_proof",
        )

    # Follow-up vendor read
    follow = _follow_up_membership_count(
        action=action,
        data=data,
        client=client,
        org_id=org_id,
        settings=settings,
        environment_name=environment_name,
        ctx=ctx,
    )
    if follow is None:
        return PopulationVerifyResult(
            verified=False,
            effect="accepted_async",
            membership_count=0,
            detail="follow_up_unavailable_or_async",
            follow_up_attempted=False,
        )
    if follow < 0:
        return PopulationVerifyResult(
            verified=False,
            effect="accepted_async",
            membership_count=0,
            detail="follow_up_rate_limited_or_error",
            follow_up_attempted=True,
        )
    if follow == 0:
        return PopulationVerifyResult(
            verified=False,
            effect="unknown",
            membership_count=0,
            detail="follow_up_empty_membership",
            follow_up_attempted=True,
        )
    return PopulationVerifyResult(
        verified=True,
        effect="created",
        membership_count=follow,
        detail="follow_up_membership_confirmed",
        follow_up_attempted=True,
    )


def _follow_up_membership_count(
    *,
    action: str,
    data: dict[str, Any],
    client: Any,
    org_id: str | None,
    settings: Any,
    environment_name: str,
    ctx: Any,
) -> int | None:
    """Return membership count, -1 on soft failure, None if not attempted."""
    list_id = ""
    bags: list[dict[str, Any]] = [data]
    for key in ("data", "structured", "result", "record", "list"):
        nested = data.get(key)
        if isinstance(nested, dict):
            bags.append(nested)
    for bag in bags:
        candidate = str(
            bag.get("list_id") or bag.get("listId") or bag.get("id") or ""
        ).strip()
        if candidate:
            list_id = candidate
            break
    if not list_id:
        return None

    try:
        if action.startswith("hubspot.") and ctx is not None:
            from app.services.tool_service import invoke_tool

            # HubSpot list membership size via contacts search filter is heavy;
            # use lists.get when available, else accept async.
            try:
                out = invoke_tool(
                    ctx,
                    "hubspot.lists.get",
                    {"list_id": list_id},
                )
                payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
                size = (
                    payload.get("size")
                    or payload.get("membershipCount")
                    or payload.get("meta", {}).get("size")
                    if isinstance(payload.get("meta"), dict)
                    else None
                )
                if size is None and isinstance(payload.get("list"), dict):
                    size = payload["list"].get("size") or payload["list"].get("additionalProperties", {}).get(
                        "hs_list_size"
                    )
                if size is not None:
                    return max(0, int(size))
            except Exception as exc:  # noqa: BLE001
                logger.info("hubspot list follow-up failed list_id=%s err=%s", list_id, exc)
                return -1

        if action.startswith("apollo.") and ctx is not None:
            from app.services.tool_service import invoke_tool

            try:
                out = invoke_tool(
                    ctx,
                    "apollo.lists.list",
                    {"list_id": list_id},
                )
                payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
                # Prefer explicit counts; else treat non-empty contact arrays as proof.
                for key in ("contact_count", "contacts_count", "member_count", "count"):
                    if payload.get(key) is not None:
                        return max(0, int(payload.get(key) or 0))
                contacts = payload.get("contacts") or payload.get("people") or []
                if isinstance(contacts, list):
                    return len(contacts)
            except Exception as exc:  # noqa: BLE001
                logger.info("apollo list follow-up failed list_id=%s err=%s", list_id, exc)
                return -1
    except Exception as exc:  # noqa: BLE001
        logger.info("collection population follow-up skipped action=%s err=%s", action, exc)
        return -1

    _ = (client, org_id, settings, environment_name)
    return None


def apply_population_verify_to_status(
    *,
    status: str,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    client: Any = None,
    org_id: str | None = None,
    settings: Any = None,
    environment_name: str = "production",
    ctx: Any = None,
) -> tuple[str, str, PopulationVerifyResult | None]:
    """Maybe downgrade completed → partial_success / keep effect honesty labels.

    Returns (status, outcome_effect_override_or_empty, verify_result).
    """
    if not is_population_write_action(invoke_action):
        return status, "", None
    if str(status or "").strip().lower() not in {"completed", "success"}:
        return status, "", None

    verify = verify_collection_population(
        invoke_action=invoke_action,
        result_data=result_data,
        client=client,
        org_id=org_id,
        settings=settings,
        environment_name=environment_name,
        ctx=ctx,
    )
    if verify.verified:
        return status, "created", verify
    if verify.effect == "accepted_async":
        return "partial_success", "accepted_async", verify
    return "partial_success", "unknown", verify
