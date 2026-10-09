"""Canonical effective WRITE approval — one resolver over HITL + identity + ActionSpec.

Duplicate settings (HITL rows, trust_level, approval_rule_overrides, F1 risk)
must not invent a fourth policy table. This module is the composition point
immediately before ReAct/tool invocation decides to block vs invoke.

Invariant: no custom HITL policy does **not** mean unrestricted WRITE.
Unattended WRITE requires explicit identity authorization (autonomous +
auto_run override) and must still yield to high-risk F1 always-approval.
"""
from __future__ import annotations

from typing import Any, Literal

from app.connectors.action_catalog.f1_write_slice import requires_write_approval_always
from app.services.agent_identity_service import (
    EffectiveAgentIdentity,
    resolve_approval_override,
)
from app.services.hitl_policy_service import HitlDecision
from app.services.org_approval_rules import ApprovalRules, is_customer_email_action

AutonomyLabel = Literal["READ ONLY", "ACT WITH APPROVAL", "ACT WITHIN POLICY"]


def autonomy_label(
    *,
    trust_level: str | None,
    unattended_write_authorized: bool,
) -> AutonomyLabel:
    if str(trust_level or "") == "read_only":
        return "READ ONLY"
    if unattended_write_authorized:
        return "ACT WITHIN POLICY"
    return "ACT WITH APPROVAL"


def resolve_write_user_approval(
    *,
    is_write: bool,
    invoke_action: str,
    action_kind: str,
    hitl: HitlDecision | None,
    identity: EffectiveAgentIdentity | None,
    risk_class: str = "",
    rules: ApprovalRules | None = None,
) -> tuple[bool, str]:
    """Return (requires_user_approval, reason).

    ``rules`` are the org's Settings > Human in the loop switches; the email
    rule holds customer email for a person even under an auto-run override.

    Callers still run HMAC / PendingAction after this returns True.
    """
    if not is_write:
        return False, "not_a_write"

    if requires_write_approval_always(invoke_action, risk_class=risk_class):
        return True, "high_risk_or_f1_write_always_requires_approval"

    if rules is not None and rules.customer_email_approval and is_customer_email_action(invoke_action):
        return True, "org_rule_customer_email_waits_for_approval"

    trust = str(identity.trust_level) if identity is not None else ""
    if trust == "read_only":
        return True, "agent_trust_read_only"

    override = resolve_approval_override(identity, action_kind)
    if override in {"always_approve", "always_deny"}:
        return True, f"identity_override_{override}"

    if trust == "write_with_approval":
        return True, "agent_trust_write_with_approval"

    hitl_matched = bool(hitl and hitl.matched_policy_id)
    if hitl_matched:
        return True, hitl.reason if hitl else "hitl_policy_matched"

    # Explicit unattended: autonomous principal + auto_run override, and no
    # covering HITL policy. Absence of HITL alone is not authorization.
    if override == "auto_run" and trust == "autonomous":
        return False, "identity_auto_run_autonomous"

    if hitl is None:
        return True, "fail_closed_missing_org_context"

    return True, hitl.reason or "no_explicit_unattended_authorization"


def snapshot_governance_fields(
    *,
    trust_level: str | None = None,
    hitl: HitlDecision | None = None,
    identity: EffectiveAgentIdentity | None = None,
) -> dict[str, Any]:
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="",
        action_kind="write",
        hitl=hitl,
        identity=identity,
        risk_class="",
    )
    unattended = not requires and reason == "identity_auto_run_autonomous"
    return {
        "writeRequiresApprovalByDefault": True,
        "noHitlPolicyMeans": "ACT WITH APPROVAL",
        "effectiveAutonomyLabel": autonomy_label(
            trust_level=trust_level or (identity.trust_level if identity else None),
            unattended_write_authorized=unattended,
        ),
        "unattendedWriteAuthorized": unattended,
        "reason": reason,
        "hitlMatchedPolicyId": hitl.matched_policy_id if hitl else None,
        "trustLevel": trust_level or (identity.trust_level if identity else None),
        "provenance": {
            "hitl": "hitl_policies",
            "trust": "agent_identity_records.trust_level",
            "overrides": "agent_identity_records.approval_rule_overrides",
            "highRisk": "ActionSpec.risk_class + f1_write_slice.requires_write_approval_always",
            "operatorExecutionMode": "operators.execution_mode (workflow auto-execute, not invoke_tool)",
        },
    }
