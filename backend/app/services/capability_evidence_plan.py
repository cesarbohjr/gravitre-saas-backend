"""P4 — required live-provider evidence before JIT/KF ranking."""
from __future__ import annotations

import re
from typing import Any

# Semantic class, not golden-phrase needles. Paraphrases must match.
_CEO_OPS_RE = re.compile(
    r"(?is)"
    r"(?:"
    r"how(?:'s|s| is| are)\s+(?:my |the |our )?(?:business|company|org(?:anization)?|pipeline)\b"
    r"|how(?:'s|s| is| are)\s+we\s+doing"
    r"|(?:my |the |our )?(?:business|company|org(?:anization)?)\s+(?:doing|performance|health|snapshot)"
    r"|business\s+performance"
    r"|company\s+performance"
    r"|performance\s+snapshot"
    r"|what should i (?:worry|watch|focus)"
    r"|ops review"
    r"|how(?:'s|s| is)\s+(?:the |my |our )?company"
    r")"
)
_NOT_CEO_RE = re.compile(
    r"(?i)\b("
    r"connector(?:s)?|oauth|sign[- ]?in|reconnect|"
    r"workflow named|run the workflow|create (?:an? )?agent"
    r")\b"
)

_HUBSPOT_KEYS = ("hubspot",)
_ADS_KEYS = ("google_ads", "google-ads", "googleads")
_GA_KEYS = ("google_analytics", "ga4", "analytics")
_GSC_KEYS = ("google_search_console", "search_console", "gsc")

# Registry / LIVE tool names that satisfy the evidence step.
HUBSPOT_TOOLS = ("hubspot.deals.list", "hubspot_deals_list", "listDeals")
ADS_TOOLS = ("google_ads.campaigns.list", "google_ads_campaigns_list")

_INTERNAL_TOOL_NEEDLES = (
    "searchknowledgebase",
    "getworkflowruns",
    "listworkflow",
    "getagentstatus",
    "listagents",
    "connector_status",
    "listconnectors",
    "getconnector",
    "getpipelinestatus",
)


def p4_evidence_plan_enabled(settings: Any | None) -> bool:
    if settings is None:
        return True
    return bool(getattr(settings, "convergence_p4_evidence_plan_v1", True))


def _norm_connected(connected: list[str] | None) -> set[str]:
    return {str(x or "").strip().lower().replace("-", "_") for x in (connected or []) if x}


def looks_like_ceo_ops_question(message: str) -> bool:
    text = " ".join((message or "").lower().split())
    if not text:
        return False
    if _NOT_CEO_RE.search(text) and not _CEO_OPS_RE.search(text):
        return False
    return bool(_CEO_OPS_RE.search(text))


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


def apply_evidence_plan_handoffs(task_state: dict[str, Any] | None, plan: dict[str, Any] | None) -> None:
    """Queue required live READs so ReAct executes them without a second model pick."""
    if not isinstance(task_state, dict) or not plan:
        return
    queue: list[dict[str, Any]] = []
    for step in plan.get("required") or []:
        names = [str(n) for n in (step.get("tool_names") or []) if n]
        if not names:
            names = [str(step.get("action_key") or "")]
        underscored = [n for n in names if "_" in n and "." not in n]
        tool_name = (underscored[0] if underscored else names[0]) if names else ""
        if not tool_name:
            continue
        queue.append(
            {
                "tool_name": tool_name,
                "tool_invoke_action": str(step.get("action_key") or tool_name),
                "tool_arguments": {},
                "fallthrough_reason": "evidence_plan_required_read",
                "single_selection": True,
            }
        )
    if queue:
        from app.services.live_classical_handoff import stash_handoff_queue

        stash_handoff_queue(task_state, queue)
        task_state["capability_evidence_plan"] = plan


def is_internal_status_tool(name: str) -> bool:
    n = str(name or "").lower().replace("-", "_").replace(".", "")
    return any(needle.replace("_", "") in n.replace("_", "") for needle in _INTERNAL_TOOL_NEEDLES)


def strip_internal_tools(visible: list[Any], plan: dict[str, Any] | None) -> list[Any]:
    if not plan or plan.get("kf_may_substitute"):
        return visible
    out = []
    for t in visible or []:
        fn = (t or {}).get("function") if isinstance(t, dict) else None
        name = str((fn or {}).get("name") or "")
        if is_internal_status_tool(name):
            continue
        out.append(t)
    return out


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
