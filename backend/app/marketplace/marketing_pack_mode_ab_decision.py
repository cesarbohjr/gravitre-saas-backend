"""STA-294 / MKT-PACK DECISION: Mode A/B feedback product sign-off checklist."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Literal

from app.marketplace.marketing_pack_feedback_loop_gaps import audit_marketing_pack_feedback_loop
from app.marketplace.pack_pricing import MODE_B_AUTONOMOUS_ADDON_CENTS

DecisionStatus = Literal["resolved", "pending", "blocked"]
SignOffState = Literal["awaiting", "approved", "rejected"]


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

    rows: list[dict[str, Any]] = []
    pending_count = 0
    blocked_count = 0

    for item in MODE_AB_DECISION_CHECKLIST:
        live_blocked = False
        if item.key == "feedback_mode_toggle":
            live_blocked = feedback_audit["summary"]["awaitingProductSignOff"]
        elif item.key in guardrail_keys:
            live_blocked = guardrail_keys[item.key] in mode_b_missing

        status = item.status
        if item.category == "guardrail" and live_blocked:
            status = "blocked"
        if item.category == "engineering" and live_blocked:
            status = "blocked"

        if status == "pending":
            pending_count += 1
        elif status == "blocked":
            blocked_count += 1

        rows.append(
            {
                "key": item.key,
                "displayName": item.display_name,
                "category": item.category,
                "status": status,
                "engineeringRecommendation": item.engineering_recommendation,
                "notes": item.notes,
            }
        )

    pricing_documented = _module_has_symbol(
        "app.marketplace.pack_pricing",
        "MODE_B_AUTONOMOUS_ADDON_CENTS",
    )

    return {
        "issue": "STA-294",
        "packSlug": "marketing-operations-pack",
        "engineeringAuditIssue": "STA-293",
        "assignTo": "Product owner for Marketing Operations Pack",
        "signOffState": "awaiting",
        "engineeringRecommendedDefault": "mode_a",
        "summary": {
            "total": len(rows),
            "pending": pending_count,
            "blocked": blocked_count,
            "resolved": len(rows) - pending_count - blocked_count,
            "modeBShippingDecisionPending": True,
            "modeBInfrastructureReady": len(mode_b_missing) == 0,
            "modeBGuardrailsImplemented": not mode_b_missing,
            "pricingPlaceholderDocumented": pricing_documented,
            "canShipModeADefault": True,
            "canShipModeB": False,
        },
        "decisions": rows,
        "feedbackLoopAudit": {
            "modeAMissing": feedback_audit["summary"]["modeA"]["missing"],
            "modeBMissing": feedback_audit["summary"]["modeB"]["missing"],
            "packBlockers": feedback_audit["summary"]["packBlockers"],
        },
    }
