"""App access rules derived from org billing status."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.billing.entitlement_service import resolve_billing_state

ACCESS_GRANT_STATUSES = frozenset({"active", "trialing", "free", "inactive"})
ACCESS_DENY_STATUSES = frozenset({"cancelled", "canceled", "trial_expired"})


def normalize_billing_status(status: str | None) -> str:
    """Return a lowercase billing status string with a safe default."""
    value = (status or "trialing").strip().lower()
    if value == "canceled":
        return "cancelled"
    return value or "trialing"


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_app_access(
    billing_status: str | None,
    *,
    trial_ends_at: Any = None,
    sandbox_exempt: bool = False,
    plan_code: str | None = None,
) -> dict[str, bool | str | None]:
    """Map billing state to frontend entitlement flags."""
    state = resolve_billing_state(
        billing_row={
            "billing_status": normalize_billing_status(billing_status),
            "plan_code": plan_code or "node",
        },
        trial_ends_at=_parse_iso_datetime(trial_ends_at),
        sandbox_exempt=sandbox_exempt,
    )

    if state["is_blocked"]:
        reason = "trial_expired" if state["status"] == "trial_expired" else (
            "payment_past_due" if state["status"] == "past_due" else "subscription_cancelled"
        )
        return {
            "can_access_app": False,
            "requires_upgrade": True,
            "upgrade_reason": reason,
        }

    status = str(state["status"])
    if status == "past_due":
        return {
            "can_access_app": False,
            "requires_upgrade": True,
            "upgrade_reason": "payment_past_due",
        }

    return {
        "can_access_app": True,
        "requires_upgrade": False,
        "upgrade_reason": None,
    }
