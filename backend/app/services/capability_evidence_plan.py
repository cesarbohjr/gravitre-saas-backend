"""P4 — required live-provider evidence before JIT/KF ranking."""
from __future__ import annotations

from typing import Any

_CEO_OPS_NEEDLES = (
    "how is my business",
    "how is the business",
    "how's the business",
    "hows the business",
    "what should i worry",
    "how are we doing",
    "business doing",
    "ops review",
    "how is the company",
)

_HUBSPOT_KEYS = ("hubspot",)
_ADS_KEYS = ("google_ads", "google-ads", "googleads")
_GA_KEYS = ("google_analytics", "ga4", "analytics")
_GSC_KEYS = ("google_search_console", "search_console", "gsc")

# Registry / LIVE tool names that satisfy the evidence step.
HUBSPOT_TOOLS = ("hubspot.deals.list", "hubspot_deals_list", "listDeals")
ADS_TOOLS = ("google_ads.campaigns.list", "google_ads_campaigns_list")


def p4_evidence_plan_enabled(settings: Any | None) -> bool:
    if settings is None:
        return True
    return bool(getattr(settings, "convergence_p4_evidence_plan_v1", True))


def _norm_connected(connected: list[str] | None) -> set[str]:
    return {str(x or "").strip().lower().replace("-", "_") for x in (connected or []) if x}


def looks_like_ceo_ops_question(message: str) -> bool:
    text = " ".join((message or "").lower().split())
    return any(n in text for n in _CEO_OPS_NEEDLES)


def _has_any(connected: set[str], keys: tuple[str, ...]) -> bool:
    return any(k in connected or any(k in c for c in connected) for k in keys)


def build_capability_evidence_plan(
    message: str,
    *,
    connected_integrations: list[str] | None,
    connector_status: dict[str, Any] | None = None,
    settings: Any | None = None,
) -> dict[str, Any] | None:
    """Return a required-evidence list for CEO/ops NL. None if not this class of turn."""
    if not p4_evidence_plan_enabled(settings):
        return None
    if not looks_like_ceo_ops_question(message):
        return None
    connected = _norm_connected(connected_integrations)
    status = connector_status if isinstance(connector_status, dict) else {}
    required: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    def _status_for(keys: tuple[str, ...]) -> str:
        for k in keys:
            raw = status.get(k)
            if isinstance(raw, dict):
                return str(raw.get("status") or raw.get("health") or "").lower()
            if isinstance(raw, str) and raw:
                return raw.lower()
        return ""

    if _has_any(connected, _HUBSPOT_KEYS):
        required.append(
            {
                "provider": "hubspot",
                "action_key": "hubspot.deals.list",
                "tool_names": list(HUBSPOT_TOOLS),
                "kind": "live_read",
            }
        )
    ads_st = _status_for(_ADS_KEYS)
    if _has_any(connected, _ADS_KEYS) and ads_st not in {"pending_auth", "disconnected"}:
        required.append(
            {
                "provider": "google_ads",
                "action_key": "google_ads.campaigns.list",
                "tool_names": list(ADS_TOOLS),
                "kind": "live_read",
            }
        )
    for label, keys in (("google_analytics", _GA_KEYS), ("google_search_console", _GSC_KEYS)):
        st = _status_for(keys)
        if st in {"pending_auth", "needs_reconnect", "disconnected"} or (
            not _has_any(connected, keys) and st == "pending_auth"
        ):
            blocked.append(
                {
                    "provider": label,
                    "status": st or "pending_auth",
                    "kind": "pending_auth",
                }
            )
        elif not _has_any(connected, keys):
            blocked.append(
                {
                    "provider": label,
                    "status": "pending_auth",
                    "kind": "pending_auth",
                }
            )

    pin_tools: list[str] = []
    for step in required:
        pin_tools.extend(str(n) for n in step.get("tool_names") or [])
    return {
        "kind": "capability_evidence_plan",
        "objective": "ceo_ops",
        "required": required,
        "blocked": blocked,
        "pin_tools": pin_tools,
        "kf_may_substitute": False,
        "honest_pending_auth": [b["provider"] for b in blocked],
    }


def pin_tools_for_evidence(visible: list[Any], all_tools: list[Any], plan: dict[str, Any] | None) -> list[Any]:
    if not plan or not plan.get("pin_tools"):
        return visible
    wanted = {str(n).lower() for n in plan["pin_tools"]}
    have: set[str] = set()
    out = list(visible or [])
    for t in out:
        fn = (t or {}).get("function") if isinstance(t, dict) else None
        name = str((fn or {}).get("name") or "").lower()
        if name:
            have.add(name)
    for t in all_tools or []:
        fn = (t or {}).get("function") if isinstance(t, dict) else None
        name = str((fn or {}).get("name") or "")
        if name.lower() in wanted and name.lower() not in have:
            out.insert(0, t)
            have.add(name.lower())
    return out


def pending_auth_prose(plan: dict[str, Any] | None) -> str:
    if not plan:
        return ""
    names = list(plan.get("honest_pending_auth") or [])
    if not names:
        return ""
    labels = ", ".join(names)
    return (
        f"I don't have a live {labels} connection yet (sign-in still pending), "
        "so traffic from those sources isn't in this answer."
    )
