"""Decision queue enrichment: real policy and decision facts per queue item."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.services.decision_queue_enrichment import enrich_decision_queue


class _Query:
    def __init__(self, rows: list[dict[str, Any]], fail: bool = False):
        self._rows = list(rows)
        self._fail = fail

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self._rows = [r for r in self._rows if str(r.get(key)) == str(value)]
        return self

    def in_(self, key, values):
        wanted = {str(v) for v in values}
        self._rows = [r for r in self._rows if str(r.get(key)) in wanted]
        return self

    def execute(self):
        if self._fail:
            raise RuntimeError("table missing")
        return SimpleNamespace(data=self._rows)


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]], failing: set[str] | None = None):
        self.tables = tables
        self.failing = failing or set()
        self.calls: list[str] = []

    def table(self, name: str):
        self.calls.append(name)
        return _Query(self.tables.get(name, []), fail=name in self.failing)


def _workflow_item(run_id: str, status: str = "pending") -> dict[str, Any]:
    return {"id": run_id, "gate_type": "execute", "status": status, "context": {"run_id": run_id}}


def test_hitl_policy_attached_from_policy_row():
    client = _Client(
        {
            "hitl_policies": [
                {
                    "id": "pol-1",
                    "org_id": "org-1",
                    "name": "Connector writes need approval",
                    "enabled": True,
                    "scope_type": "org",
                    "action_kinds": ["write", "delete"],
                    "approver_roles": ["admin", "owner"],
                    "required_approvals": 1,
                }
            ]
        }
    )
    items = [
        {
            "id": "a-1",
            "gate_type": "chat_connector_write",
            "status": "pending",
            "context": {"hitl_policy_id": "pol-1", "hitl_action_kind": "write"},
        }
    ]
    enrich_decision_queue(client, "org-1", items)
    policy = items[0]["policy"]
    assert policy["source"] == "hitl"
    assert policy["name"] == "Connector writes need approval"
    assert policy["scope"] == "org"
    assert policy["action_kind"] == "write"
    assert items[0]["decisions"] == []


def test_connector_write_without_policy_uses_safe_default_and_extension_confirm():
    client = _Client({})
    items = [
        {"id": "a-1", "gate_type": "chat_connector_write", "status": "pending", "context": {}},
        {
            "id": "a-2",
            "gate_type": "browser_extension_write",
            "status": "pending",
            "context": {"requires_approval": True},
        },
    ]
    enrich_decision_queue(client, "org-1", items)
    assert items[0]["policy"]["source"] == "hitl_default"
    assert items[0]["policy"]["approver_roles"] == ["admin", "owner"]
    assert items[1]["policy"]["source"] == "extension_confirm"
    # No policy ids → no hitl query; no workflow items → no approval_policies query.
    assert "hitl_policies" not in client.calls
    assert "approval_policies" not in client.calls


def test_workflow_policy_scope_and_recorded_decision_override_review_fields():
    client = _Client(
        {
            "approval_policies": [
                {"id": "ap-org", "org_id": "org-1", "workflow_id": None, "required_approvals": 1,
                 "approver_roles": ["admin"], "run_types": ["execute"]},
                {"id": "ap-wf", "org_id": "org-1", "workflow_id": "wf-1", "required_approvals": 2,
                 "approver_roles": ["owner"], "run_types": ["execute"]},
            ],
            "run_approvals": [
                {"run_id": "run-2", "org_id": "org-1", "approver_id": "u-9", "status": "rejected",
                 "comment": "Wrong list", "created_at": "2026-10-01T10:00:00+00:00"},
            ],
            "users": [{"id": "u-9", "full_name": "Dana Reviewer", "email": "dana@example.com"}],
        }
    )
    items = [_workflow_item("run-1"), _workflow_item("run-2", status="rejected")]
    items[1]["reviewed_at"] = "2026-09-01T00:00:00+00:00"  # run created_at placeholder
    enrich_decision_queue(
        client,
        "org-1",
        items,
        run_meta={
            "run-1": {"workflow_id": "wf-1", "required_approvals": 2},
            "run-2": {"workflow_id": "wf-other", "required_approvals": 1},
        },
    )
    assert items[0]["policy"]["scope"] == "workflow"
    assert items[0]["policy"]["required_approvals"] == 2
    assert items[1]["policy"]["scope"] == "org"
    assert items[1]["reviewed_at"] == "2026-10-01T10:00:00+00:00"
    assert items[1]["reviewed_by_name"] == "Dana Reviewer"
    assert items[1]["review_comment"] == "Wrong list"
    assert items[1]["decisions"][0]["status"] == "rejected"


def test_enrichment_degrades_when_tables_fail():
    client = _Client({}, failing={"approval_policies", "run_approvals", "hitl_policies"})
    items = [
        _workflow_item("run-1"),
        {"id": "a-1", "gate_type": "chat_connector_write", "status": "pending",
         "context": {"hitl_policy_id": "pol-x"}},
    ]
    enrich_decision_queue(client, "org-1", items, run_meta={"run-1": {"workflow_id": "wf-1", "required_approvals": 1}})
    assert items[0]["policy"]["scope"] == "default"
    assert items[0]["decisions"] == []
    assert items[1]["policy"] == {"source": "hitl", "id": "pol-x", "name": None, "missing": True, "action_kind": "write"}


def test_workflow_steps_come_from_the_definition_snapshot():
    client = _Client({})
    items = [_workflow_item("run-plan")]
    snapshot = {
        "source": "chat_orchestration",
        "steps": [
            {"id": "s1", "name": "Search HubSpot for high-intent leads", "invoke_action": "hubspot.contacts.search"},
            {"id": "s2", "name": "Post a short summary to a channel", "invoke_action": "slack.chat.postMessage"},
        ],
    }
    enrich_decision_queue(
        client,
        "org-1",
        items,
        run_meta={"run-plan": {"required_approvals": 1, "definition_snapshot": snapshot}},
    )
    steps = items[0]["steps"]
    assert [s["text"] for s in steps] == [
        "Search HubSpot for high-intent leads",
        "Post a short summary to a channel",
    ]
    assert [s["app"] for s in steps] == ["hubspot", "slack"]
    assert steps[0]["access"] == "read"
    assert steps[1]["access"] == "write"
    assert items[0]["context"]["risk_level"] == "medium"
    assert items[0]["context"]["risk_derived"] is True


def test_read_only_plan_is_low_risk_and_two_approvers_is_high():
    client = _Client({})
    read_only = {"steps": [{"name": "Look up deals", "invoke_action": "hubspot.deals.search"}]}
    items = [_workflow_item("run-a"), _workflow_item("run-b")]
    enrich_decision_queue(
        client,
        "org-1",
        items,
        run_meta={
            "run-a": {"required_approvals": 1, "definition_snapshot": read_only},
            "run-b": {"required_approvals": 2, "definition_snapshot": read_only},
        },
    )
    assert items[0]["context"]["risk_level"] == "low"
    assert items[1]["context"]["risk_level"] == "high"


def test_stored_risk_wins_and_connector_write_gets_one_step():
    client = _Client({})
    items = [
        {
            "id": "a-9",
            "title": "Delete contact",
            "gate_type": "chat_connector_write",
            "status": "pending",
            "context": {
                "invoke_action": "hubspot.contacts.delete",
                "integration": "hubspot",
                "label": "Delete a contact",
                "risk_level": "medium",
            },
        },
        {
            "id": "a-10",
            "title": "Delete contact",
            "gate_type": "chat_connector_write",
            "status": "pending",
            "context": {"invoke_action": "hubspot.contacts.delete", "integration": "hubspot"},
        },
    ]
    enrich_decision_queue(client, "org-1", items)
    assert items[0]["steps"] == [
        {"text": "Delete a contact", "action": "hubspot.contacts.delete", "app": "hubspot", "access": "write"}
    ]
    assert items[0]["context"]["risk_level"] == "medium"
    assert "risk_derived" not in items[0]["context"]
    assert items[1]["context"]["risk_level"] == "high"
