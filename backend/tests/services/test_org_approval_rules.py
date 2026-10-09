"""Settings v5: org approval rules, notification matrix and ops notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest

from app.services.hitl_policy_service import HitlDecision, apply_org_rules
from app.services.notification_preference_service import (
    flatten_structured_preferences,
    structured_preferences,
)
from app.services.org_approval_rules import (
    DEFAULT_RULES,
    ApprovalRules,
    definition_has_high_risk_step,
    is_customer_email_action,
    merge_rules_update,
    rules_from_settings,
    sla_deadline,
)
from app.services.write_governance import resolve_write_user_approval


def _decision(kind: str, *, requires: bool = True, required: int = 1) -> HitlDecision:
    return HitlDecision(
        requires_approval=requires,
        matched_policy_id="p1",
        matched_policy_name="Org writes",
        action_kind=kind,
        required_approvals=required,
        approver_roles=["admin"],
        approver_user_ids=[],
        reason="Matched HITL policy",
    )


def test_defaults_keep_todays_behaviour():
    rules = rules_from_settings({})
    assert rules == DEFAULT_RULES
    assert rules.two_approvals_high_risk is False
    assert rules.auto_approve_read_only is False
    assert rules.escalate_past_due is False
    assert rules.sla_minutes == 240


def test_merge_rules_update_validates_and_keeps_other_fields():
    rules = merge_rules_update(DEFAULT_RULES, {"twoApprovalsHighRisk": True, "sla": "1h"})
    assert rules.two_approvals_high_risk is True
    assert rules.sla_minutes == 60
    assert rules.customer_email_approval is True
    with pytest.raises(ValueError):
        merge_rules_update(DEFAULT_RULES, {"sla": "2 weeks"})
    with pytest.raises(ValueError):
        merge_rules_update(DEFAULT_RULES, {"escalatePastDue": "yes"})
    stored = rules_from_settings({"approvalRules": rules.to_api()})
    assert stored == rules


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("gmail.send_message", True),
        ("outlook.send_mail", True),
        ("email.send", True),
        ("gmail.drafts.create", False),
        ("slack.chat.postMessage", False),
        ("hubspot.contacts.create", False),
    ],
)
def test_customer_email_detection(action: str, expected: bool):
    assert is_customer_email_action(action) is expected


def test_high_risk_definition_detection():
    assert definition_has_high_risk_step({"steps": [{"name": "Delete stale contacts", "type": "connector"}]})
    assert definition_has_high_risk_step({"steps": [{"name": "x", "config": {"action": "stripe.refund.create"}}]})
    assert not definition_has_high_risk_step({"steps": [{"name": "Search HubSpot", "type": "connector"}]})


def test_sla_one_business_day_skips_weekend():
    friday = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)  # Friday
    rules = ApprovalRules(sla="1bd")
    deadline = sla_deadline(friday, rules, "America/Vancouver")
    assert deadline.astimezone(timezone.utc).weekday() == 0  # Monday
    assert sla_deadline(friday, ApprovalRules(sla="1h"), "UTC") == datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)


def test_auto_approve_read_only_rule():
    read = _decision("read")
    assert apply_org_rules(read, DEFAULT_RULES).requires_approval is True
    relaxed = apply_org_rules(read, ApprovalRules(auto_approve_read_only=True))
    assert relaxed.requires_approval is False
    assert relaxed.required_approvals == 0


def test_two_approvals_for_deletes_only():
    rules = ApprovalRules(two_approvals_high_risk=True)
    assert apply_org_rules(_decision("delete"), rules).required_approvals == 2
    assert apply_org_rules(_decision("write"), rules).required_approvals == 1
    assert apply_org_rules(_decision("delete"), DEFAULT_RULES).required_approvals == 1


def test_customer_email_rule_holds_autonomous_agents():
    identity = type("Identity", (), {"trust_level": "autonomous", "approval_rule_overrides": {}})()
    with patch("app.services.write_governance.resolve_approval_override", return_value="auto_run"):
        allowed, _ = resolve_write_user_approval(
            is_write=True,
            invoke_action="gmail.send_message",
            action_kind="write",
            hitl=_decision("write", requires=False),
            identity=identity,
            rules=ApprovalRules(customer_email_approval=False),
        )
        held, reason = resolve_write_user_approval(
            is_write=True,
            invoke_action="gmail.send_message",
            action_kind="write",
            hitl=_decision("write", requires=False),
            identity=identity,
            rules=ApprovalRules(customer_email_approval=True),
        )
    assert held is True
    assert reason == "org_rule_customer_email_waits_for_approval"
    # With the rule off the outcome falls through to the existing resolver.
    assert isinstance(allowed, bool)


def test_partial_preference_update_keeps_other_events():
    stored = flatten_structured_preferences({"task_completed": {"bell_enabled": False, "email_enabled": True}})
    updated = flatten_structured_preferences(
        {"run_failed": {"bell_enabled": True, "email_enabled": False, "slack_enabled": True}},
        stored,
    )
    view = structured_preferences(updated)
    assert view["task_completed"] == {"bell_enabled": False, "email_enabled": True, "slack_enabled": False}
    assert view["run_failed"]["slack_enabled"] is True
    assert view["run_failed"]["email_enabled"] is False
    assert view["source_attention"]["bell_enabled"] is True
    assert view["weekly_summary"]["email_enabled"] is False


class _Query:
    def __init__(self, db: "_FakeDb", table: str) -> None:
        self.db = db
        self.table = table
        self.filters: list[tuple[str, str, Any]] = []
        self.update_payload: dict[str, Any] | None = None
        self.order_key: str | None = None
        self.window: tuple[int, int] | None = None

    def order(self, key: str, **_k: Any) -> "_Query":
        self.order_key = key
        return self

    def range(self, start: int, end: int) -> "_Query":
        self.window = (start, end)
        return self

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def eq(self, key: str, value: Any) -> "_Query":
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key: str, value: Any) -> "_Query":
        self.filters.append(("in", key, value))
        return self

    def gte(self, *_a: Any) -> "_Query":
        return self

    def limit(self, *_a: Any) -> "_Query":
        return self

    def update(self, payload: dict[str, Any]) -> "_Query":
        self.update_payload = payload
        return self

    def _rows(self) -> list[dict[str, Any]]:
        rows = self.db.tables.get(self.table, [])
        out = []
        for row in rows:
            ok = True
            for op, key, value in self.filters:
                if op == "eq" and row.get(key) != value:
                    ok = False
                if op == "in" and row.get(key) not in value:
                    ok = False
            if ok:
                out.append(row)
        if self.order_key:
            out.sort(key=lambda row: str(row.get(self.order_key) or ""))
        if self.window:
            out = out[self.window[0] : self.window[1] + 1]
        return out

    def execute(self) -> Any:
        rows = self._rows()
        if self.update_payload is not None:
            for row in rows:
                row.update(self.update_payload)
        return type("Result", (), {"data": rows, "count": len(rows)})()


class _FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def test_escalation_notifies_admins_once():
    from app.services import ops_notifications

    db = _FakeDb(
        {
            "organizations": [
                {"id": "org-1", "settings": {"approvalRules": {"escalatePastDue": True, "sla": "1h"}}}
            ],
            "workflow_runs": [
                {
                    "id": "run-1",
                    "org_id": "org-1",
                    "approval_status": "pending_approval",
                    "created_at": "2026-10-09T08:00:00+00:00",
                    "definition_snapshot": {"name": "Send renewals"},
                }
            ],
            "approvals": [],
            "organization_members": [
                {"org_id": "org-1", "user_id": "admin-1", "role": "admin"},
                {"org_id": "org-1", "user_id": "member-1", "role": "member"},
            ],
        }
    )
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    with patch.object(ops_notifications, "emit_notification", return_value="n1") as emit:
        assert ops_notifications.escalate_past_due_approvals(db, "org-1", now=now) == 1
        assert ops_notifications.escalate_past_due_approvals(db, "org-1", now=now) == 0
    assert emit.call_count == 1
    assert emit.call_args.kwargs["user_id"] == "admin-1"
    assert emit.call_args.kwargs["entity_ref"]["result_url"] == "/approvals?id=run-1"


def test_weekly_summary_sends_once_on_monday_morning():
    from app.services import ops_notifications

    org = {"id": "org-1", "settings": {"timezone": "UTC"}}
    db = _FakeDb(
        {
            "organizations": [org],
            "organization_members": [{"org_id": "org-1", "user_id": "u1", "role": "member"}],
        }
    )
    sunday = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
    monday = datetime(2026, 10, 12, 9, 30, tzinfo=timezone.utc)
    with patch.object(ops_notifications, "emit_notification", return_value="n1") as emit:
        assert ops_notifications.send_weekly_summary_if_due(db, org, now=sunday) == 0
        assert ops_notifications.send_weekly_summary_if_due(db, org, now=monday) == 1
        again = db.tables["organizations"][0]
        assert ops_notifications.send_weekly_summary_if_due(db, again, now=monday) == 0
    assert emit.call_args.kwargs["event_type"] == "weekly_summary"


def test_escalation_keeps_settings_saved_meanwhile_and_reaches_old_requests():
    from app.services import ops_notifications

    org = {"id": "org-1", "settings": {"approvalRules": {"escalatePastDue": True, "sla": "1h"}}}
    stale = dict(org["settings"])
    # An admin changes the time zone after the tick read its snapshot.
    org["settings"] = {**org["settings"], "timezone": "Europe/London"}
    runs = [
        {
            "id": f"run-{i:03d}",
            "org_id": "org-1",
            "approval_status": "pending_approval",
            "created_at": f"2026-10-0{1 + i // 100}T{i % 24:02d}:00:00+00:00",
            "definition_snapshot": {"name": f"Run {i}"},
        }
        for i in range(450)
    ]
    db = _FakeDb(
        {
            "organizations": [org],
            "workflow_runs": runs,
            "approvals": [],
            "organization_members": [{"org_id": "org-1", "user_id": "admin-1", "role": "admin"}],
        }
    )
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    with patch.object(ops_notifications, "emit_notification", return_value="n1"):
        sent = ops_notifications.escalate_past_due_approvals(db, "org-1", now=now, org_settings=stale)
    assert sent == 450
    saved = db.tables["organizations"][0]["settings"]
    assert saved["timezone"] == "Europe/London"
    assert "run-000" in saved["opsNotifications"]["escalated"]


def test_weekly_summary_claim_survives_a_stale_snapshot():
    from app.services import ops_notifications

    org = {"id": "org-1", "settings": {"timezone": "UTC", "opsNotifications": {"weeklySummaryWeek": "2026-W42"}}}
    db = _FakeDb({"organizations": [org], "organization_members": [{"org_id": "org-1", "user_id": "u1", "role": "member"}]})
    monday = datetime(2026, 10, 12, 9, 30, tzinfo=timezone.utc)
    stale = {"id": "org-1", "settings": {"timezone": "UTC"}}
    with patch.object(ops_notifications, "emit_notification", return_value="n1") as emit:
        assert ops_notifications.send_weekly_summary_if_due(db, stale, now=monday) == 0
    emit.assert_not_called()


def test_more_than_500_overdue_requests_escalate_once():
    from app.services import ops_notifications

    org = {"id": "org-1", "settings": {"approvalRules": {"escalatePastDue": True, "sla": "1h"}}}
    runs = [
        {
            "id": f"run-{i:04d}",
            "org_id": "org-1",
            "approval_status": "pending_approval",
            "created_at": f"2026-09-{1 + i // 100:02d}T{i % 24:02d}:{i % 60:02d}:00+00:00",
        }
        for i in range(700)
    ]
    db = _FakeDb(
        {
            "organizations": [org],
            "workflow_runs": runs,
            "approvals": [],
            "organization_members": [{"org_id": "org-1", "user_id": "admin-1", "role": "admin"}],
        }
    )
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    with patch.object(ops_notifications, "emit_notification", return_value="n1"):
        assert ops_notifications.escalate_past_due_approvals(db, "org-1", now=now) == 700
        assert ops_notifications.escalate_past_due_approvals(db, "org-1", now=now) == 0
        # The next escalation forgets requests that were decided meanwhile.
        runs[0]["approval_status"] = "approved"
        runs.append({"id": "run-new", "org_id": "org-1", "approval_status": "pending_approval", "created_at": "2026-10-09T09:00:00+00:00"})
        assert ops_notifications.escalate_past_due_approvals(db, "org-1", now=now) == 1
    escalated = db.tables["organizations"][0]["settings"]["opsNotifications"]["escalated"]
    assert "run-0000" not in escalated and "run-0699" in escalated and "run-new" in escalated
