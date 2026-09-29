"""Effective WRITE approval: no custom HITL policy is not unrestricted WRITE."""
from __future__ import annotations

from app.connectors.action_catalog.f1_write_slice import requires_write_approval_always
from app.services.agent_identity_service import EffectiveAgentIdentity
from app.services.hitl_policy_service import HitlDecision
from app.services.write_governance import (
    autonomy_label,
    resolve_write_user_approval,
)


def _identity(**kwargs) -> EffectiveAgentIdentity:
    base = dict(
        org_id="org-1",
        agent_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        trust_level="write_with_approval",
        allowed_tool_patterns=("*",),
        allowed_action_kinds=frozenset({"read", "write"}),
        allowed_data_scopes=(),
        max_actions_per_day=None,
        max_tokens_per_day=None,
        max_spend_usd_per_day=None,
        can_delegate=False,
        approval_rule_overrides={},
    )
    base.update(kwargs)
    return EffectiveAgentIdentity(**base)


def _hitl(*, matched: bool = False, requires: bool = True) -> HitlDecision:
    return HitlDecision(
        requires_approval=requires,
        matched_policy_id="p1" if matched else None,
        matched_policy_name="Org write" if matched else None,
        action_kind="write",
        required_approvals=1 if requires else 0,
        approver_roles=["admin"] if requires else [],
        approver_user_ids=[],
        reason="No HITL policies configured (approval required)" if not matched else "Matched",
    )


def test_no_policy_write_requires_approval():
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=_hitl(matched=False),
        identity=None,
    )
    assert requires is True
    assert "unattended" not in reason
    assert autonomy_label(trust_level=None, unattended_write_authorized=False) == "ACT WITH APPROVAL"


def test_read_does_not_require_approval():
    requires, reason = resolve_write_user_approval(
        is_write=False,
        invoke_action="apollo.contacts.search",
        action_kind="read",
        hitl=_hitl(matched=False, requires=False),
        identity=None,
    )
    assert requires is False
    assert reason == "not_a_write"


def test_explicit_auto_run_autonomous_allows_unattended_standard_write():
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=_hitl(matched=False),
        identity=_identity(trust_level="autonomous", approval_rule_overrides={"write": "auto_run"}),
    )
    assert requires is False
    assert reason == "identity_auto_run_autonomous"
    assert autonomy_label(trust_level="autonomous", unattended_write_authorized=True) == "ACT WITHIN POLICY"


def test_autonomous_without_auto_run_still_requires_approval():
    requires, _reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=_hitl(matched=False),
        identity=_identity(trust_level="autonomous"),
    )
    assert requires is True


def test_matched_hitl_beats_auto_run():
    requires, _reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=_hitl(matched=True),
        identity=_identity(trust_level="autonomous", approval_rule_overrides={"write": "auto_run"}),
    )
    assert requires is True


def test_high_risk_f1_write_always_requires_approval():
    assert requires_write_approval_always("gmail.messages.send") is True
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="gmail.messages.send",
        action_kind="write",
        hitl=_hitl(matched=False),
        identity=_identity(trust_level="autonomous", approval_rule_overrides={"write": "auto_run"}),
    )
    assert requires is True
    assert reason == "high_risk_or_f1_write_always_requires_approval"


def test_read_only_trust_requires_approval():
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=_hitl(matched=False),
        identity=_identity(trust_level="read_only"),
    )
    assert requires is True
    assert reason == "agent_trust_read_only"
    assert autonomy_label(trust_level="read_only", unattended_write_authorized=False) == "READ ONLY"


def test_missing_org_context_fail_closed():
    requires, reason = resolve_write_user_approval(
        is_write=True,
        invoke_action="apollo.lists.create",
        action_kind="write",
        hitl=None,
        identity=None,
    )
    assert requires is True
    assert reason == "fail_closed_missing_org_context"
