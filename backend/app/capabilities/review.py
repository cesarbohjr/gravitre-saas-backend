"""Org-admin review policy for portable capability packages."""
from __future__ import annotations


def review_transition_allowed(
    *,
    current_status: str,
    target_status: str,
    risk_level: str,
    license_policy: str,
) -> bool:
    target = str(target_status or "").strip().lower()
    if target not in {"installed", "quarantined", "disabled"}:
        return False
    if target == "installed" and (
        str(license_policy or "").strip().lower() == "block"
        or str(risk_level or "").strip().lower() == "blocked"
    ):
        return False
    return str(current_status or "").strip().lower() != "removed"
