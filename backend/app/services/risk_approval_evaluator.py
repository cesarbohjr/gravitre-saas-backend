"""Pre-execution risk and approval evaluation."""
from __future__ import annotations

from typing import Any

from app.billing.entitlement_service import assert_org_not_blocked
from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client


class RiskApprovalEvaluator:
    """
    Consolidates entitlement, persona, and action risk checks before Stage 9 execution.
    Does not replace Approvals — determines whether approval is required.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def evaluate(
        self,
        org_id: str,
        user_id: str,
        action: dict[str, Any],
        classification: dict[str, Any],
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        _ = user_id
        client = get_supabase_client(self.settings)
        assert_org_not_blocked(client, org_id)

        action_type = str(action.get("type") or action.get("action") or "unknown")
        persona_requires_list = persona.get("requires_approval_for") or []
        persona_requires = action_type in persona_requires_list
        if persona.get("advisory_only"):
            persona_requires = persona_requires or "all_actions" in persona_requires_list

        risk = str(classification.get("risk_level") or "low")
        requires = (
            persona_requires
            or risk == "high"
            or bool(action.get("is_financial"))
            or bool(action.get("is_customer_facing"))
            or bool(action.get("is_destructive"))
            or bool(classification.get("requires_approval"))
        )
        return {
            "requires_approval": requires,
            "risk_level": risk,
            "approval_reason": (
                f"Action type '{action_type}' requires approval per {persona.get('role', 'policy')}"
                if requires
                else None
            ),
            "can_proceed_without_approval": not requires,
            "approval_type": action_type if requires else None,
            "estimated_impact": str(action.get("estimated_impact") or "low"),
        }


_risk_approval_evaluator: RiskApprovalEvaluator | None = None


def get_risk_approval_evaluator(settings: Settings | None = None) -> RiskApprovalEvaluator:
    global _risk_approval_evaluator
    if _risk_approval_evaluator is None or settings is not None:
        _risk_approval_evaluator = RiskApprovalEvaluator(settings)
    return _risk_approval_evaluator
