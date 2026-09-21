"""Website objective + source readiness (connected ≠ executable)."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings

WEBSITE_VENDORS = ("google_analytics", "google_search_console")


def classify_vendor_readiness(row: dict[str, Any] | None) -> dict[str, Any]:
    item = row if isinstance(row, dict) else {}
    auth = str(item.get("auth_status") or "").strip().lower()
    reason = str(item.get("blocking_reason") or "").strip().lower()
    executable = bool(item.get("execution_available"))
    connected = auth in {"connected", "authorized"} or str(item.get("status") or "").lower() in {
        "connected",
        "healthy",
        "active",
    }
    token_valid = executable or (connected and reason not in {"token_expired", "auth_expired"} and auth not in {
        "auth_expired",
        "pending_auth",
        "not_authenticated",
    })
    authorized = auth not in {"pending_auth", "not_connected", "disconnected", "inactive"} and bool(item)
    return {
        "vendor": item.get("vendor"),
        "connected": bool(connected and item),
        "authorized": bool(authorized),
        "token_valid": bool(token_valid and item),
        "executable": executable,
        "capability_suitable": True,
        "auth_status": auth or None,
        "blocking_reason": reason or None,
        "present": bool(item),
    }


def website_source_readiness(
    client: Any,
    org_id: str,
    settings: Settings | None = None,
) -> dict[str, dict[str, Any]]:
    from app.connectors.connector_availability_service import list_connector_availability

    by_vendor: dict[str, dict[str, Any]] = {
        vendor: classify_vendor_readiness(None) | {"vendor": vendor, "present": False}
        for vendor in WEBSITE_VENDORS
    }
    try:
        rows = list_connector_availability(
            client,
            org_id,
            settings or get_settings(),
            environment_name="production",
            force_live=True,
        )
    except Exception:  # noqa: BLE001 — never fail the turn on inventory
        return by_vendor
    for row in rows:
        vendor = str(row.get("vendor") or "").strip().lower()
        if vendor not in by_vendor:
            continue
        classified = classify_vendor_readiness(row)
        if classified["executable"] or not by_vendor[vendor].get("executable"):
            by_vendor[vendor] = classified
    return by_vendor


def any_website_source_executable(readiness: dict[str, dict[str, Any]]) -> bool:
    return any(bool((readiness.get(v) or {}).get("executable")) for v in WEBSITE_VENDORS)


def website_limitation_message(readiness: dict[str, dict[str, Any]], *, timeframe: str | None = None) -> str:
    ga = readiness.get("google_analytics") or {}
    gsc = readiness.get("google_search_console") or {}
    window = f" for {timeframe}" if timeframe else ""
    lines = [
        f"I'm still on website performance{window}. No website analytics system is executable on this workspace right now.",
        "",
    ]
    lines.append(f"- **Analytics:** {_vendor_clause(ga, 'Google Analytics')}")
    lines.append(f"- **Search Console:** {_vendor_clause(gsc, 'Search Console')}")
    lines.append("")
    lines.append(
        "Other connected systems are not used for this question. "
        "Reconnect Analytics or Search Console, then ask the same website question again."
    )
    return "\n".join(lines)


def website_frame_patch(*, objective: str, readiness: dict[str, dict[str, Any]], timeframe: str | None = None) -> dict[str, Any]:
    return {
        "active_analysis": {
            "kind": "analytics.traffic_overview",
            "objective": "website_performance",
            "objective_text": objective,
            "timeframe": timeframe,
            "website_source_status": {
                vendor: {
                    "connected": row.get("connected"),
                    "authorized": row.get("authorized"),
                    "token_valid": row.get("token_valid"),
                    "executable": row.get("executable"),
                    "auth_status": row.get("auth_status"),
                    "blocking_reason": row.get("blocking_reason"),
                }
                for vendor, row in readiness.items()
            },
        }
    }


def _vendor_clause(row: dict[str, Any], label: str) -> str:
    if not row.get("present"):
        return f"{label} isn't connected."
    if row.get("executable"):
        return f"{label} is executable."
    reason = str(row.get("blocking_reason") or row.get("auth_status") or "not executable")
    if reason in {"pending_auth", "not_connected"}:
        return f"{label} is present but not authorized yet (pending sign-in)."
    if reason in {"token_expired", "auth_expired"}:
        return f"{label} is connected but the sign-in expired. Reconnect it at /connectors."
    return f"{label} is not executable ({reason.replace('_', ' ')})."
