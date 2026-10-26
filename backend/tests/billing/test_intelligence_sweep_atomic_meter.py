"""Offline subscription gate and atomic sweep usage acceptance (no Stripe/network)."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.billing.intelligence_sweep_meter import entitled_sweep_limit, reserve_sweep, settle_sweep


class DB:
    def __init__(self, answer=None, error=None):
        self.answer = {"id": "sweep-1", "org_id": "org-a", "status": "queued"} if answer is None else answer
        self.error = error
        self.calls = []
    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return self
    def execute(self):
        if self.error:
            raise RuntimeError(self.error)
        return SimpleNamespace(data=self.answer)


def test_active_subscription_enforces_effective_plan_quota():
    with patch("app.billing.service.get_org_billing", return_value={
        "plan_code": "control", "billing_status": "active",
    }), patch("app.billing.service.get_plan_for_org", return_value={
        "code": "control", "features": {"intelligence_sweeps_per_month": 12},
    }), patch("app.billing.entitlement_service._load_trial_ends_at", return_value=None), patch(
        "app.billing.entitlement_service._is_sandbox_exempt", return_value=False
    ):
        period, allowance = entitled_sweep_limit(object(), "org-a")
    assert len(period) == 7
    assert allowance == 12


def test_inactive_subscription_cannot_admit_usage():
    client = DB()
    with patch("app.billing.service.get_org_billing", return_value={
        "plan_code": "control", "billing_status": "past_due",
    }), patch("app.billing.entitlement_service._load_trial_ends_at", return_value=None), patch(
        "app.billing.entitlement_service._is_sandbox_exempt", return_value=False
    ):
        with pytest.raises(HTTPException) as exc:
            reserve_sweep(client, "org-a", "admin-a", {})
    assert exc.value.status_code == 402
    assert client.calls == []


def test_active_quota_admission_uses_database_rpc_only():
    client = DB()
    with patch("app.billing.intelligence_sweep_meter.entitled_sweep_limit", return_value=("2026-10", 5)):
        row = reserve_sweep(client, "org-a", "admin-a", {"vendor": "hubspot"})
    assert row["id"] == "sweep-1"
    assert client.calls == [("admit_metered_intelligence_sweep", {
        "p_org_id": "org-a", "p_requested_by": "admin-a",
        "p_scope": {"vendor": "hubspot"}, "p_period": "2026-10", "p_limit": 5,
    })]


def test_quota_exceeded_and_rpc_error_fail_closed():
    with patch("app.billing.intelligence_sweep_meter.entitled_sweep_limit", return_value=("2026-10", 5)):
        with pytest.raises(HTTPException) as quota:
            reserve_sweep(DB(error="intelligence sweep entitlement exceeded"), "org-a", "admin", {})
        with pytest.raises(HTTPException) as offline:
            reserve_sweep(DB(error="database unavailable"), "org-a", "admin", {})
    assert quota.value.status_code == 402
    assert offline.value.status_code == 503


def test_settlement_is_ledger_rpc_not_client_side_increment():
    client = DB(answer=True)
    assert settle_sweep(client, "org-a", "sweep-1")
    assert client.calls[0][0] == "settle_intelligence_sweep_unit"
    assert client.calls[0][1] == {
        "p_org_id": "org-a", "p_sweep_id": "sweep-1", "p_state": "settled",
    }
    client = DB(answer=False)
    assert not settle_sweep(client, "org-a", "sweep-1")


def test_sweep_without_reserved_unit_must_not_start_provider_work():
    from app.services.intelligence_overview_sweep_worker import process_queued_sweep
    with patch("app.services.intelligence_overview_sweep_worker._has_reserved_sweep_unit", return_value=False), patch(
        "app.services.intelligence_overview_sweep_worker.assessment_for_org"
    ) as analyze:
        result = process_queued_sweep(object(), {
            "id": "sweep-old", "org_id": "org-a", "status": "queued",
        })
    assert result["status"] == "billing_reservation_missing"
    analyze.assert_not_called()


def test_successful_work_does_not_reexecute_after_settlement_outage():
    from app.services.intelligence_overview_sweep_worker import process_queued_sweep
    class Query:
        def __init__(self, state):
            self.state = state
            self.filters = {}
            self.updated = None
        def update(self, data):
            self.updated = data
            return self
        def eq(self, k, v):
            self.filters[k] = v
            return self
        def execute(self):
            if all(self.state.get(k) == v for k,v in self.filters.items()):
                self.state.update(self.updated)
                return SimpleNamespace(data=[dict(self.state)])
            return SimpleNamespace(data=[])
    class Fake:
        def __init__(self): self.state = {"id": "s-1", "org_id": "org-a", "status": "queued"}
        def table(self, name):
            assert name == "intelligence_overview_sweeps"
            return Query(self.state)
    db = Fake()
    with patch("app.services.intelligence_overview_sweep_worker._has_reserved_sweep_unit", return_value=True), patch(
        "app.services.intelligence_overview_sweep_worker.assessment_for_org",
        return_value={"advisory_only": True}
    ) as assessment, patch(
        "app.services.intelligence_overview_sweep_worker._settle_completed_sweep",
        side_effect=RuntimeError("temporary ledger outage")
    ):
        first = process_queued_sweep(db, dict(db.state))
        second = process_queued_sweep(db, dict(db.state))
    assert first["status"] == "partial"
    assert second["status"] == "already_claimed"
    assessment.assert_called_once()


def test_usage_snapshot_includes_in_flight_reservations():
    from app.billing.intelligence_sweep_meter import sweep_usage_snapshot
    class Ledger:
        def table(self, name):
            assert name == "intelligence_sweep_usage_ledger"
            return self
        def select(self, *_): return self
        def eq(self, *_): return self
        def in_(self, *_): return self
        def limit(self, *_): return self
        def execute(self):
            return SimpleNamespace(data=[{"units": 1, "state": "reserved"}, {"units": 1, "state": "settled"}])
    with patch("app.billing.intelligence_sweep_meter.entitled_sweep_limit", return_value=("2026-10", 5)):
        result = sweep_usage_snapshot(Ledger(), "org-a")
    assert result["used"] == 2
    assert result["remaining"] == 3
    assert result["source"] == "atomic_usage_ledger"
