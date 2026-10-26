"""Offline evidence -> canonical Play -> approvals -> outcome lookup contract."""
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services.intelligence_evidence_recommendations import build_evidence_recommendations
from app.routers import intelligence_overview as overview


def fixtures():
    rows = [
        {"org_id": "org-a", "connector_id": "crm", "object_type": "contact", "external_id": "c1"},
        {"org_id": "org-a", "connector_id": "support", "object_type": "contact", "external_id": "u1"},
    ]
    matches = [{
        "org_id": "org-a", "identity_kind": "email", "identity_hash": "a" * 64,
        "match_status": "verified_key",
        "record_references": [
            {"connector_id": "crm", "object_type": "contact", "external_id": "c1"},
            {"connector_id": "support", "object_type": "contact", "external_id": "u1"},
        ],
    }]
    return rows, matches


def test_grounded_recommendation_has_provenance_but_no_fabricated_benefit():
    rows, matches = fixtures()
    recs = build_evidence_recommendations(rows, matches, org_id="org-a")
    assert len(recs) == 1
    item = recs[0]
    assert item["recommended_play_key"] == "customer-rescue"
    assert item["approval_required"]
    assert item["business_impact"] is None
    assert item["outcome_verified"] is False
    assert len(item["sources"]) == 2


def test_cross_tenant_and_missing_source_evidence_fail_closed():
    rows, matches = fixtures()
    assert build_evidence_recommendations(rows, matches, org_id="org-b") == []
    assert build_evidence_recommendations(rows[:1], matches, org_id="org-a") == []


@pytest.mark.asyncio
async def test_approved_handoff_calls_canonical_play_runner_not_direct_write(monkeypatch):
    rows, matches = fixtures()
    recommendation = build_evidence_recommendations(rows, matches, org_id="org-a")[0]
    monkeypatch.setattr(overview, "_verified_evidence_recommendations",
                        lambda db, org: [recommendation] if org == "org-a" else [])
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = SimpleNamespace(data=[{"id": "handoff-1"}])
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[{"id": "handoff-1"}])
    monkeypatch.setattr(overview, "_db", lambda _: client)
    play_response = {"playRunId": "play-run-1", "status": "awaiting_approval", "workflowRuns": [
        {"approvalRequired": True, "status": "pending_approval"}]}
    with patch("app.routers.plays.run_play", new_callable=AsyncMock, return_value=play_response) as runner:
        result = await overview.execute_evidence_recommendation(
            recommendation["id"], overview.RecommendationPlayRequest(installation_id="install-a"),
            "org-a", ({"user_id": "admin-a"}, "org-a", "admin"), "production", object())
    assert runner.await_count == 1
    assert runner.await_args.args[0] == "customer-rescue"
    assert result["playRun"] == play_response
    assert result["handoffId"] == "handoff-1"
    client.table.return_value.insert.assert_called_once()
    assert result["verifiedBusinessOutcome"] is False
    assert result["outcomesHref"] == "/api/plays/customer-rescue/outcomes"


@pytest.mark.asyncio
async def test_unrecognized_recommendation_never_invokes_execution(monkeypatch):
    monkeypatch.setattr(overview, "_db", lambda _: object())
    monkeypatch.setattr(overview, "_verified_evidence_recommendations", lambda *_: [])
    with patch("app.routers.plays.run_play", new_callable=AsyncMock) as runner:
        with pytest.raises(HTTPException) as exc:
            await overview.execute_evidence_recommendation(
                "from-other-tenant", overview.RecommendationPlayRequest(installation_id="install-a"),
                "org-a", ({"user_id": "admin-a"}, "org-a", "admin"), "production", object())
    assert exc.value.status_code == 404
    runner.assert_not_awaited()


def test_outcome_readback_does_not_upgrade_unverified_event(monkeypatch):
    client = MagicMock()
    response = SimpleNamespace(data=[{
        "id": "link-1", "org_id": "org-a", "recommendation_id": "r-1",
        "play_key": "customer-rescue", "play_run_id": "play-1",
        "workflow_run_ids": ["workflow-1"], "status": "submitted",
    }])
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = response
    monkeypatch.setattr(overview, "_db", lambda _: client)
    with patch("app.plays.outcomes.list_play_business_results", return_value=[{
        "id": "outcome-1", "workflow_run_id": "workflow-1",
        "metadata": {"verification_state": "PENDING VERIFICATION"},
    }]), patch("app.plays.evidence.build_play_evidence_chain") as evidence:
        result = overview.evidence_recommendation_handoffs(
            "r-1", "org-a", ({"sub": "member"}, "org-a", "member"), object())
    assert result["count"] == 1
    assert result["handoffs"][0]["verifiedBusinessOutcome"] is False
    evidence.assert_not_called()


def test_outcome_readback_requires_real_source_evidence(monkeypatch):
    client = MagicMock()
    response = SimpleNamespace(data=[{
        "id": "link-1", "org_id": "org-a", "recommendation_id": "r-1",
        "play_key": "customer-rescue", "play_run_id": "play-1",
        "workflow_run_ids": ["workflow-1"], "status": "submitted",
    }])
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = response
    monkeypatch.setattr(overview, "_db", lambda _: client)
    event = {
        "id": "outcome-1", "workflow_run_id": "workflow-1",
        "metadata": {"verification_state": "VERIFIED SUCCESS"},
    }
    with patch("app.plays.outcomes.list_play_business_results", return_value=[event]), patch(
        "app.plays.evidence.build_play_evidence_chain", return_value=None
    ):
        result = overview.evidence_recommendation_handoffs(
            "r-1", "org-a", ({"sub": "member"}, "org-a", "member"), object())
    assert result["handoffs"][0]["verifiedBusinessOutcome"] is False
    with patch("app.plays.outcomes.list_play_business_results", return_value=[event]), patch(
        "app.plays.evidence.build_play_evidence_chain", return_value={"verification": {"verified": True, "state": "VERIFIED SUCCESS", "method": "provider_readback"}, "sourceRecords": [{"system": "hubspot", "record_id": "rec-1"}], "metric": {"key": "retained_accounts", "baseline": 1, "result": 2}}
    ):
        result = overview.evidence_recommendation_handoffs(
            "r-1", "org-a", ({"sub": "member"}, "org-a", "member"), object())
    assert result["handoffs"][0]["verifiedBusinessOutcome"] is True


@pytest.mark.asyncio
async def test_duplicate_recommendation_preclaim_blocks_canonical_runtime(monkeypatch):
    rows, matches = fixtures()
    rec = build_evidence_recommendations(rows, matches, org_id="org-a")[0]
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("duplicate")
    monkeypatch.setattr(overview, "_verified_evidence_recommendations", lambda *_: [rec])
    monkeypatch.setattr(overview, "_db", lambda _: db)
    with patch("app.routers.plays.run_play", new_callable=AsyncMock) as runner:
        with pytest.raises(HTTPException) as exc:
            await overview.execute_evidence_recommendation(
                rec["id"], overview.RecommendationPlayRequest(installation_id="install-a"),
                "org-a", ({"user_id": "admin-a"}, "org-a", "admin"), "production", object())
    assert exc.value.status_code == 409
    runner.assert_not_awaited()
