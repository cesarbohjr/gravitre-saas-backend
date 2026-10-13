"""Event-triggered runs are attributed to an accountable member, deterministically."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.automation_actor import configured_by_from_parameters, resolve_automation_actor


class _C:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _n):
        return self

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def order(self, *_a):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


ROWS = [
    {"user_id": "m1", "role": "member", "created_at": "1"},
    {"user_id": "o1", "role": "owner", "created_at": "2"},
    {"user_id": "a1", "role": "admin", "created_at": "3"},
    {"user_id": "o2", "role": "owner", "created_at": "4"},
]


def test_configuring_admin_wins():
    assert resolve_automation_actor(_C(ROWS), "org", configured_by="a1", workflow_created_by="m1") == "a1"


def test_configurer_demoted_to_member_is_skipped_for_creator():
    assert resolve_automation_actor(_C(ROWS), "org", configured_by="m1", workflow_created_by="m1") == "m1"


def test_creator_who_left_falls_back_to_earliest_owner():
    assert resolve_automation_actor(_C(ROWS), "org", configured_by="gone", workflow_created_by="gone") == "o1"


def test_never_returns_org_id_or_viewer():
    rows = [{"user_id": "v", "role": "viewer", "created_at": "1"}]
    assert resolve_automation_actor(_C(rows), "org", workflow_created_by="v") is None


def test_configured_by_read_from_trigger_binding():
    assert configured_by_from_parameters({"trigger": {"configured_by": "a1"}}) == "a1"
    assert configured_by_from_parameters({"trigger": {}}) is None
    assert configured_by_from_parameters(None) is None
