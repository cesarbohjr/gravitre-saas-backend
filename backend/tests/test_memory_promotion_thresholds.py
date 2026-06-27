from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_promotion_service import (
    AUTO_GLOSSARY_PROVENANCE,
    MemoryPromotionService,
    MemoryPromotionStatus,
)


def _service() -> MemoryPromotionService:
    return MemoryPromotionService(settings=MagicMock())


def _mock_client_for_glossary(*, frequency: int, dept_count: int, departments: list[str]):
    client = MagicMock()
    term_row = {
        "id": "term-1",
        "term": "QBR",
        "term_type": "acronym",
        "frequency": frequency,
    }

    def table(name):
        t = MagicMock()
        if name == "org_glossary_terms":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[term_row]
            )
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[term_row])
        elif name == "user_query_patterns":
            rows = [
                {
                    "department": dept,
                    "query_text": f"find {term_row['term']} deck",
                    "normalized_query_text": f"find {term_row['term'].lower()} deck",
                }
                for dept in departments
                for _ in range(max(1, frequency // max(len(departments), 1)))
            ]
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=rows)
        elif name == "agents":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": f"agent-{departments[0]}"}]
            )
        elif name == "memory_promotion_candidates":
            stored: dict = {}

            def insert(payload):
                row = {**payload, "id": "cand-1"}
                stored["row"] = row
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[row])
                return chain

            def select(*args, **kwargs):
                chain = MagicMock()
                chain.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[]
                )
                chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                return chain

            def update(payload):
                if "row" in stored:
                    stored["row"].update(payload)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=[stored.get("row")])
                return chain

            t.insert.side_effect = insert
            t.select.side_effect = select
            t.update.side_effect = update
        elif name == "agent_memories":
            t.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "mem-1", "provenance": AUTO_GLOSSARY_PROVENANCE}]
            )
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        return t

    client.table.side_effect = table
    return client


@pytest.mark.asyncio
async def test_glossary_term_below_threshold_goes_pending_not_auto():
    service = _service()
    client = _mock_client_for_glossary(frequency=8, dept_count=1, departments=["Marketing"])
    with patch.object(service, "_client", return_value=client):
        result = await service.evaluate_glossary_candidates("org-1")
    assert result["auto_promoted"] == 0
    assert result["pending_approval"] == 1


@pytest.mark.asyncio
async def test_glossary_term_above_threshold_auto_promotes():
    service = _service()
    client = _mock_client_for_glossary(
        frequency=25, dept_count=2, departments=["Marketing", "Sales"]
    )
    with patch.object(service, "_client", return_value=client), patch.object(
        service, "_count_departments_for_term", return_value=2
    ), patch.object(
        service, "_departments_for_term", return_value={"Marketing", "Sales"}
    ), patch.object(
        service,
        "_upsert_candidate",
        return_value={"id": "cand-1", "metadata": {"term": "QBR", "departments": ["Marketing", "Sales"]}},
    ), patch.object(
        service,
        "_promote_candidate",
        return_value={"candidate_id": "cand-1", "memory_ids": ["mem-1"]},
    ) as promote:
        result = await service.evaluate_glossary_candidates("org-1")
    assert result["auto_promoted"] == 1
    promote.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_pattern_never_auto_promotes():
    service = _service()
    client = MagicMock()
    pending_candidate = {
        "id": "cand-wf",
        "candidate_type": "workflow_pattern",
        "status": MemoryPromotionStatus.PENDING_APPROVAL.value,
    }

    def table(name):
        t = MagicMock()
        if name == "workflow_runs":
            t.select.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
                data=[
                    {"workflow_id": "wf-1", "status": "failed", "error_message": "timeout"},
                    {"workflow_id": "wf-1", "status": "failed", "error_message": "timeout"},
                    {"workflow_id": "wf-1", "status": "failed", "error_message": "timeout"},
                ]
            )
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client), patch.object(
        service, "_upsert_candidate", return_value=pending_candidate
    ):
        created = await service.detect_workflow_pattern_candidates("org-1")
    assert created
    assert created[0]["status"] == MemoryPromotionStatus.PENDING_APPROVAL.value
    with pytest.raises(ValueError, match="Only glossary"):
        service._promote_candidate(
            client,
            created[0],
            org_id="org-1",
            promotion_path="auto",
            decision_reasoning="should fail",
            threshold_snapshot={},
            provenance="v4:auto:workflow_pattern",
            expires_at=None,
            status_at_decision=MemoryPromotionStatus.AUTO_PROMOTED.value,
        )


@pytest.mark.asyncio
async def test_successful_response_never_auto_promotes():
    service = _service()
    client = MagicMock()
    pending_candidate = {
        "id": "cand-resp",
        "candidate_type": "successful_response",
        "status": MemoryPromotionStatus.PENDING_APPROVAL.value,
    }

    def table(name):
        t = MagicMock()
        if name == "user_query_patterns":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "normalized_query_text": "reset vpn",
                        "query_text": "reset vpn",
                        "feedback_helpful": True,
                        "rag_quality_score": 0.9,
                    }
                ]
                * 4
            )
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client), patch.object(
        service, "_upsert_candidate", return_value=pending_candidate
    ):
        created = await service.detect_successful_response_candidates("org-1")
    assert created
    assert created[0]["status"] == MemoryPromotionStatus.PENDING_APPROVAL.value
