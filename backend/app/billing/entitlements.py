"""App access rules derived from org billing status."""
from __future__ import annotations

ACCESS_GRANT_STATUSES = frozenset({"active", "trialing", "free", "inactive"})
ACCESS_DENY_STATUSES = frozenset({"cancelled", "canceled"})


def normalize_billing_status(status: str | None) -> str:
    """Return a lowercase billing status string with a safe default."""
    value = (status or "trialing").strip().lower()
    if value == "canceled":
        return "cancelled"
    return value or "trialing"


def compute_app_access(billing_status: str | None) -> dict[str, bool | str | None]:
    """Map billing status to frontend entitlement flags.

    Returns:
        can_access_app: Whether the user may use the product shell.
        requires_upgrade: Whether an upgrade prompt should be shown.
        upgrade_reason: Machine-readable reason when upgrade is suggested.
    """
    status = normalize_billing_status(billing_status)

    if status in ACCESS_GRANT_STATUSES:
        return {
            "can_access_app": True,
            "requires_upgrade": False,
            "upgrade_reason": None,
        }

    if status == "past_due":
        return {
            "can_access_app": True,
            "requires_upgrade": True,
            "upgrade_reason": "payment_past_due",
        }

    if status in ACCESS_DENY_STATUSES:
        return {
            "can_access_app": False,
            "requires_upgrade": True,
            "upgrade_reason": "subscription_cancelled",
        }

    return {
        "can_access_app": True,
        "requires_upgrade": False,
        "upgrade_reason": None,
    }
