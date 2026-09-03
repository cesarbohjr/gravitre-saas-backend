"""Unit tests for joined run observability (no new logging store)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.run_observability_service import build_run_observability


def test_build_run_observability_joins_shards_without_cot():
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.order.return_value = mock
        mock.limit.return_value = mock
        if name == "audit_events":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "a1",
                        "action": "tool.invoke.completed",
                        "actor_id": "u1",
                        "resource_type": "workflow_run",
                        "resource_id": "run-1",
                        "metadata": {
                            "action": "hubspot.lists.create",
                            "connector_id": "c1",
                            "thought": "SECRET_COT",
                        },
                        "created_at": "2026-09-03T12:00:00Z",
                    },
                    {
                        "id": "a2",
                        "action": "agent.handoff.completed",
                        "actor_id": "u1",
                        "resource_type": "workflow_run",
                        "resource_id": "run-1",
                        "metadata": {
                            "from_agent_id": "ag1",
                            "to_agent_id": "ag2",
                            "chain_of_thought": "PRIVATE",
                        },
                        "created_at": "2026-09-03T12:01:00Z",
                    },
                ]
            )
        elif name == "cognitive_turn_traces":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "turn_id": "t1",
                        "surface": "chat",
                        "stages": [
                            {
                                "stage": "knowledge",
                                "ok": True,
                                "ms": 12,
                                "meta": {"thought": "PRIVATE", "sources": ["pack:msp"]},
                            }
                        ],
                        "knowledge_summary": {"sources": ["pack:msp"]},
                        "confidence_summary": {"score": 0.8},
                        "conversation_id": "conv-1",
                        "created_at": "2026-09-03T11:59:00Z",
                    }
                ]
            )
        elif name == "intelligence_outcome_events":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "outcome_event": "completed",
                        "model_name": "gpt-test",
                        "confidence_score": 0.81,
                        "metadata": {"cost_usd": 0.02},
                        "created_at": "2026-09-03T12:02:00Z",
                    }
                ]
            )
        else:
            mock.execute.return_value = MagicMock(data=[])
        return mock

    client.table.side_effect = table

    dto = build_run_observability(
        client,
        org_id="org-1",
        run_payload={
            "id": "run-1",
            "status": "completed",
            "duration_ms": 1500,
            "required_approvals": 1,
            "parameters": {
                "goal": "Enrich MSP Prospects",
                "conversation_id": "conv-1",
                "model": "gpt-test",
            },
            "definition_snapshot": {"name": "MSP Pros"},
        },
        steps=[
            {
                "id": "s1",
                "step_name": "Search",
                "step_type": "invoke_tool",
                "status": "completed",
                "order_index": 0,
                "started_at": "2026-09-03T12:00:00Z",
                "completed_at": "2026-09-03T12:00:10Z",
            }
        ],
    )

    assert dto["runId"] == "run-1"
    assert dto["intent"] == "Enrich MSP Prospects"
    assert dto["modelUsed"] == "gpt-test"
    assert dto["conversationId"] == "conv-1"
    assert dto["approvalsRequired"] is True
    assert dto["latencyMs"] == 1500
    assert dto["confidence"] == 0.81
    assert dto["costUsd"] == 0.02
    assert any(t.get("tool") == "hubspot.lists.create" for t in dto["toolsCalled"])
    assert dto["agentHandoffs"]
    assert "pack:msp" in dto["contextSources"]
    # Private CoT stripped from cognitive meta and handoff metadata.
    assert dto["cognitiveTurns"][0]["stages"][0]["meta"].get("thought") is None
    assert "chain_of_thought" not in dto["agentHandoffs"][0]["metadata"]
    assert dto["sources"]["audit"] == "audit_events"
    assert any(r.get("kind") == "step" for r in dto["replay"])
