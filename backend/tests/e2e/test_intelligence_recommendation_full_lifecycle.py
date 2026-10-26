"""Offline handoff lifecycle: recommendation → canonical Play request → approval wait
→ workflow attribution → source-evidence outcome readback. No live providers.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest

from app.routers import intelligence_overview as api
from app.services.intelligence_evidence_recommendations import build_evidence_recommendations


class LinkQuery:
    def __init__(self, store):
        self.store = store
        self.filters = {}
        self.inserted = None
        self.changes = None
    def insert(self, value):
        self.inserted = dict(value)
        return self
    def update(self, value):
        self.changes = dict(value)
        return self
    def select(self, *_):
        return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def limit(self, *_):
        return self
    def execute(self):
        if self.inserted is not None:
            if self.store:
                raise RuntimeError("duplicate handoff")
            row = {"id": "handoff-1", **self.inserted}
            self.store.append(row)
            return SimpleNamespace(data=[deepcopy(row)])
        rows = [r for r in self.store if all(r.get(k) == v for k, v in self.filters.items())]
        if self.changes is not None:
            for row in rows:
                row.update(self.changes)
        return SimpleNamespace(data=deepcopy(rows))


class LinkDB:
    def __init__(self):
        self.store = []
    def table(self, name):
        assert name == "intelligence_recommendation_play_links"
        return LinkQuery(self.store)


@pytest.mark.asyncio
async def test_offline_recommendation_governed_play_and_verified_outcome_readback(monkeypatch):
    records = [
        {"org_id": "org-a", "connector_id": "crm", "object_type": "contact", "external_id": "1"},
        {"org_id": "org-a", "connector_id": "support", "object_type": "contact", "external_id": "2"},
    ]
    matches = [{"org_id": "org-a", "identity_kind": "email", "identity_hash": "a" * 64,
                "match_status": "verified_key", "record_references": [
                    {"connector_id": "crm", "object_type": "contact", "external_id": "1"},
                    {"connector_id": "support", "object_type": "contact", "external_id": "2"}]}]
    rec = build_evidence_recommendations(records, matches, org_id="org-a")[0]
    db = LinkDB()
    monkeypatch.setattr(api, "_db", lambda _: db)
    monkeypatch.setattr(api, "_verified_evidence_recommendations",
                        lambda _db, org: [rec] if org == "org-a" else [])
    canonical = {"playRunId": "run-1", "status": "awaiting_approval",
                 "workflowRuns": [{"runId": "wf-1", "status": "pending_approval",
                                   "approvalRequired": True}]}
    with patch("app.routers.plays.run_play", new_callable=AsyncMock, return_value=canonical) as runner:
        submission = await api.execute_evidence_recommendation(
            rec["id"], api.RecommendationPlayRequest(installation_id="installation-1"),
            "org-a", ({"user_id": "admin-1"}, "org-a", "admin"), "production", object())
    assert runner.await_count == 1
    assert runner.await_args.args[0] == "customer-rescue"
    assert submission["playRun"]["status"] == "awaiting_approval"
    assert submission["verifiedBusinessOutcome"] is False
    assert db.store[0]["play_run_id"] == "run-1"
    assert db.store[0]["workflow_run_ids"] == ["wf-1"]

    with patch("app.plays.outcomes.list_play_business_results", return_value=[]):
        awaiting = api.evidence_recommendation_handoffs(
            rec["id"], "org-a", ({"sub": "member"}, "org-a", "member"), object())
    assert not awaiting["handoffs"][0]["verifiedBusinessOutcome"]

    event = {"id": "outcome-1", "workflow_run_id": "wf-1",
             "metadata": {"verification_state": "VERIFIED SUCCESS"}}
    with patch("app.plays.outcomes.list_play_business_results", return_value=[event]), patch(
        "app.plays.evidence.build_play_evidence_chain", return_value={"verification": {"verified": True, "state": "VERIFIED SUCCESS", "method": "provider_readback"}, "sourceRecords": [{"system": "hubspot", "record_id": "provider-record-1"}], "metric": {"key": "retained_accounts", "baseline": 1, "result": 2}}
    ):
        verified = api.evidence_recommendation_handoffs(
            rec["id"], "org-a", ({"sub": "member"}, "org-a", "member"), object())
    assert verified["handoffs"][0]["verifiedBusinessOutcome"] is True
    assert verified["handoffs"][0]["outcomes"][0]["verified"]

    cross_tenant = api.evidence_recommendation_handoffs(
        rec["id"], "org-b", ({"sub": "other-member"}, "org-b", "member"), object())
    assert cross_tenant["count"] == 0
