"""STA-294 / MKT-PACK DECISION: Mode A/B feedback product sign-off checklist."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Literal

from app.marketplace.marketing_pack_feedback_loop_gaps import audit_marketing_pack_feedback_loop
from app.marketplace.pack_pricing import MODE_B_AUTONOMOUS_ADDON_CENTS

DecisionStatus = Literal["resolved", "pending", "blocked"]
SignOffState = Literal["awaiting", "partial", "approved", "rejected"]
ModeBShippingDecision = Literal["opt_in_only", "do_not_ship"]
ModeBPricingDecision = Literal["included_with_risk_gate", "addon_4900_cents"]


PRODUCT_SIGN_OFF_LABELS: dict[str, str] = {
    "opt_in_only": "Mode B ships as opt-in only (not default; requires explicit org enablement).",
    "included_with_risk_gate": (
        "Included at Tier 2 base unlock ($149) with in-product risk-acknowledgment gate; "
        "no separate $49 add-on required for v1."
    ),
    "addon_4900_cents": "Separate one-time $49 add-on (MODE_B_AUTONOMOUS_ADDON_CENTS).",
    "do_not_ship": "Mode B does not ship for Marketing Operations Pack v1.",
    "mode_a": "Mode A (human-approved suggestions) is the pack default for all orgs.",
    "infrastructure_required_before_enable": (
        "Mode B must not be customer-enablable until guardrails and feedback toggle ship."
    ),
}


# Product owner sign-off (STA-294, 2026-06-30).
PRODUCT_SIGN_OFF: dict[str, str] = {
    "default_feedback_mode": "mode_a",
    "mode_b_shipping": "opt_in_only",
    "mode_b_pricing_model": "included_with_risk_gate",
    "mode_b_go_live_gate": "infrastructure_required_before_enable",
    "signed_at": "2026-06-30",
    "signed_by_role": "product_owner",
}


@dataclass(frozen=True)
class ModeAbDecisionItem:
    key: str
    display_name: str
    category: Literal["default", "mode_b", "guardrail", "pricing", "engineering"]
    status: DecisionStatus
    engineering_recommendation: str
    notes: str


MODE_AB_DECISION_CHECKLIST: tuple[ModeAbDecisionItem, ...] = (
    ModeAbDecisionItem(
        key="default_feedback_mode",
        display_name="Default feedback mode for Marketing Operations Pack",
        category="default",
        status="pending",
        engineering_recommendation="mode_a",
        notes="Human-approved suggestions before any agent behavior change.",
    ),
    ModeAbDecisionItem(
        key="mode_b_shipping",
        display_name="Whether Mode B (autonomous replanning) ships at all",
        category="mode_b",
        status="pending",
        engineering_recommendation="opt_in_only_if_approved",
        notes="Net-new platform work; brand-voice-affecting. Awaiting pack-owner sign-off.",
    ),
    ModeAbDecisionItem(
        key="mode_b_behavior_shift_cap",
        display_name="Cap on behavior shift per cycle",
        category="guardrail",
        status="blocked",
        engineering_recommendation="required_if_mode_b",
        notes="Guardrail required if Mode B approved; infrastructure missing (STA-293 audit).",
    ),
    ModeAbDecisionItem(
        key="mode_b_autonomous_rollback",
        display_name="Rollback if new behavior underperforms",
        category="guardrail",
        status="blocked",
        engineering_recommendation="required_if_mode_b",
        notes="Guardrail required if Mode B approved; infrastructure missing (STA-293 audit).",
    ),
    ModeAbDecisionItem(
        key="mode_b_post_hoc_audit",
        display_name="Post-hoc audit trail without approval anchor",
        category="guardrail",
        status="blocked",
        engineering_recommendation="required_if_mode_b",
        notes="Guardrail required if Mode B approved; infrastructure missing (STA-293 audit).",
    ),
    ModeAbDecisionItem(
        key="mode_b_pricing_model",
        display_name="Mode B pricing: included with risk gate vs add-on",
        category="pricing",
        status="pending",
        engineering_recommendation="included_with_risk_gate_or_addon_4900_cents",
        notes=f"Documented placeholder MODE_B_AUTONOMOUS_ADDON_CENTS={MODE_B_AUTONOMOUS_ADDON_CENTS}; no Stripe SKU.",
    ),
    ModeAbDecisionItem(
        key="mode_b_go_live_gate",
        display_name="Mode B go-live gate (guardrails + toggle required)",
        category="engineering",
        status="pending",
        engineering_recommendation="infrastructure_required_before_enable",
        notes="Product confirms Mode B is blocked until guardrails and feedback toggle ship.",
    ),
    ModeAbDecisionItem(
        key="feedback_mode_toggle",
        display_name="Org/pack feedback mode toggle (general primitive)",
        category="engineering",
        status="blocked",
        engineering_recommendation="build_after_sign_off",
        notes="Depends on product decision; missing platform-wide (STA-293 audit).",
    ),
)


def _module_has_symbol(module_path: str, symbol: str) -> bool:
    if importlib.util.find_spec(module_path) is None:
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def audit_marketing_pack_mode_ab_decision() -> dict[str, Any]:
    """Return STA-294 product decision checklist cross-checked with STA-293 engineering audit."""
    feedback_audit = audit_marketing_pack_feedback_loop()
    mode_b_missing = set(feedback_audit["summary"]["modeBMissingKeys"])
    guardrail_keys = {
        "mode_b_behavior_shift_cap": "per_cycle_behavior_caps",
        "mode_b_autonomous_rollback": "autonomous_rollback",
        "mode_b_post_hoc_audit": "post_hoc_audit_without_approval",
    }
    shipping_decision = PRODUCT_SIGN_OFF.get("mode_b_shipping")
    pricing_decision = PRODUCT_SIGN_OFF.get("mode_b_pricing_model")
    default_decision = PRODUCT_SIGN_OFF.get("default_feedback_mode")
    go_live_gate = PRODUCT_SIGN_OFF.get("mode_b_go_live_gate")

    rows: list[dict[str, Any]] = []
    pending_count = 0
    blocked_count = 0
    resolved_count = 0
    engineering_blocked_count = 0

    for item in MODE_AB_DECISION_CHECKLIST:
        live_blocked = False
        if item.key == "feedback_mode_toggle":
            live_blocked = True  # infrastructure not shipped yet
        elif item.key in guardrail_keys:
            live_blocked = guardrail_keys[item.key] in mode_b_missing

        status = item.status
        product_decision: str | None = None

        if item.key == "default_feedback_mode" and default_decision:
            status = "resolved"
            product_decision = default_decision
        elif item.key == "mode_b_shipping" and shipping_decision:
            status = "resolved"
            product_decision = shipping_decision
        elif item.key == "mode_b_pricing_model" and pricing_decision:
            status = "resolved"
            product_decision = pricing_decision
        elif item.key == "mode_b_go_live_gate" and go_live_gate:
            status = "resolved"
            product_decision = go_live_gate
        elif item.category == "guardrail" and live_blocked:
            status = "blocked"
            engineering_blocked_count += 1
        elif item.category == "engineering" and item.key == "feedback_mode_toggle" and live_blocked:
            status = "blocked"
            engineering_blocked_count += 1

        if status == "pending":
            pending_count += 1
        elif status == "blocked":
            blocked_count += 1
        else:
            resolved_count += 1

        row: dict[str, Any] = {
            "key": item.key,
            "displayName": item.display_name,
            "category": item.category,
            "status": status,
            "engineeringRecommendation": item.engineering_recommendation,
            "notes": item.notes,
        }
        if product_decision:
            row["productDecision"] = product_decision
            label = PRODUCT_SIGN_OFF_LABELS.get(product_decision)
            if label:
                row["productDecisionLabel"] = label
        rows.append(row)

    pricing_documented = _module_has_symbol(
        "app.marketplace.pack_pricing",
        "MODE_B_AUTONOMOUS_ADDON_CENTS",
    )
    mode_b_approved_opt_in = shipping_decision == "opt_in_only"
    product_sign_off_complete = all(
        PRODUCT_SIGN_OFF.get(key)
        for key in (
            "default_feedback_mode",
            "mode_b_shipping",
            "mode_b_pricing_model",
            "mode_b_go_live_gate",
        )
    )
    sign_off_state: SignOffState = "awaiting"
    if product_sign_off_complete:
        sign_off_state = "approved"

    return {
        "issue": "STA-294",
        "packSlug": "marketing-operations-pack",
        "engineeringAuditIssue": "STA-293",
        "assignTo": "Product owner for Marketing Operations Pack",
        "signOffState": sign_off_state,
        "productSignOff": dict(PRODUCT_SIGN_OFF),
        "engineeringRecommendedDefault": "mode_a",
        "packDefaultFeedbackMode": default_decision or "mode_a",
        "summary": {
            "total": len(rows),
            "pending": pending_count,
            "blocked": blocked_count,
            "resolved": resolved_count,
            "engineeringBlocked": engineering_blocked_count,
            "productSignOffComplete": product_sign_off_complete,
            "modeBShippingDecisionPending": not shipping_decision,
            "modeBShippingApproved": mode_b_approved_opt_in,
            "modeBPricingModel": pricing_decision,
            "modeBGoLiveGate": go_live_gate,
            "modeBInfrastructureReady": len(mode_b_missing) == 0,
            "modeBGuardrailsImplemented": not mode_b_missing,
            "pricingPlaceholderDocumented": pricing_documented,
            "canShipModeADefault": default_decision == "mode_a",
            "canShipModeB": mode_b_approved_opt_in and not mode_b_missing,
        },
        "decisions": rows,
        "feedbackLoopAudit": {
            "modeAMissing": feedback_audit["summary"]["modeA"]["missing"],
            "modeBMissing": feedback_audit["summary"]["modeB"]["missing"],
            "packBlockers": feedback_audit["summary"]["packBlockers"],
        },
    }
