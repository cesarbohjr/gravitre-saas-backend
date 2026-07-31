"""Unit tests for HITL policy classify + resolve."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.hitl_policy_service import (
    HitlPolicyService,
    classify_action_kind,
)


def test_classify_action_kind_delete_from_name():
    assert (
        classify_action_kind(
            kind="write",
            invoke_action="apollo.contacts.delete",
            tool_name="apollo_contacts_delete",
        )
        == "delete"
    )


def test_classify_action_kind_read():
    assert classify_action_kind(kind="read", invoke_action="apollo.contacts.search") == "read"


def test_classify_action_kind_destructive_flag():
    assert classify_action_kind(kind="write", destructive=True) == "delete"


def test_resolve_defaults_auto_run_when_no_policies():
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[])
    client.table.return_value = table

    decision = HitlPolicyService().resolve(
        client, org_id="org-1", user_id="user-1", action_kind="write"
    )
    assert decision.requires_approval is False


def test_resolve_user_policy_beats_org():
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[])
        if name == "hitl_policies":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "p-org",
                        "name": "Org write",
                        "enabled": True,
                        "scope_type": "org",
                        "action_kinds": ["write"],
                        "approver_roles": ["admin"],
                        "approver_user_ids": [],
                        "required_approvals": 1,
                    },
                    {
                        "id": "p-user",
                        "name": "User write",
                        "enabled": True,
                        "scope_type": "user",
                        "subject_user_id": "user-1",
                        "action_kinds": ["write"],
                        "approver_roles": ["owner"],
                        "approver_user_ids": ["approver-9"],
                        "required_approvals": 1,
                    },
                ]
            )
        return mock

    client.table.side_effect = table
    decision = HitlPolicyService().resolve(
        client, org_id="org-1", user_id="user-1", action_kind="write"
    )
    assert decision.matched_policy_id == "p-user"
    assert decision.approver_user_ids == ["approver-9"]
    assert decision.can_approve(role="member", user_id="approver-9") is True
    assert decision.can_approve(role="member", user_id="other") is False
    assert decision.can_approve(role="owner", user_id="other") is True


def test_resolve_department_scope():
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[])
        if name == "hitl_policies":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "p-dept",
                        "name": "Sales delete",
                        "enabled": True,
                        "scope_type": "department",
                        "department_id": "dept-sales",
                        "action_kinds": ["delete"],
                        "approver_roles": ["admin"],
                        "approver_user_ids": [],
                        "required_approvals": 1,
                    }
                ]
            )
        return mock

    client.table.side_effect = table
    decision = HitlPolicyService().resolve(
        client,
        org_id="org-1",
        user_id="user-1",
        action_kind="delete",
        department_ids=["dept-sales"],
    )
    assert decision.requires_approval is True
    assert decision.matched_policy_id == "p-dept"


def test_resolve_read_without_policy_skips_approval():
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[])
    client.table.return_value = table

    decision = HitlPolicyService().resolve(
        client, org_id="org-1", user_id="user-1", action_kind="read"
    )
    assert decision.requires_approval is False
