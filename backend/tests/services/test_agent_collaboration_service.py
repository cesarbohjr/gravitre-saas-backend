"""Internal Agent Collaboration Layer — handoff, Finance↔Marketing, mutation proofs."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.services.agent_collaboration_service import (
    COLLAB_AUDIT_CREATED,
    COLLAB_AUDIT_RECEIVER,
    COLLAB_AUDIT_RECONCILED,
    CollaborationResponseContract,
    CollaborationTaskHandoff,
    assert_ranked_context_preserved,
    build_collaboration_briefing,
    build_ranked_context_for_handoff,
    collaboration_label,
    evaluate_write_authority_for_proposed_action,
    execute_internal_collaboration_handoff,
    extract_receiver_payload,
    parse_receiver_stance,
    resolve_proposed_capability,
)
from app.services.run_observability_service import _handoffs_from_audit


def test_external_trust_boundary_rejected():
    with pytest.raises(ValidationError) as exc:
        CollaborationTaskHandoff(
            originating_agent_id="a",
            receiving_agent_id="b",
            task="check budget",
            trust_boundary="external",
        )
    assert "EXTERNAL A2A" in str(exc.value) or "gated" in str(exc.value).lower()


def test_collaboration_label_marketing_finance():
    assert collaboration_label("Marketing", "Finance") == "Marketing → Finance"


def test_build_ranked_context_includes_claim_not_raw_dump():
    ranked = build_ranked_context_for_handoff(
        task="Challenge projected CAC",
        originating_claim={
            "claim": "Projected CAC assumes 4.2% conversion",
            "projected_conversion_rate": 0.042,
        },
        extra_sources=[
            {
                "source_id": "healthcare_hist",
                "source_type": "org_context",
                "label": "Historical healthcare conversion",
                "score": 0.95,
                "content": "Historical healthcare conversion is only 2.6%",
            }
        ],
    )
    assert ranked
    blob = " ".join(item.content for item in ranked)
    assert "4.2" in blob or "0.042" in blob
    assert "2.6" in blob
    assert "full conversation transcript" not in blob.lower()


def test_assert_ranked_context_preserved_mutation():
    handoff = CollaborationTaskHandoff(
        originating_agent_id="mkt",
        receiving_agent_id="fin",
        task="Validate CAC",
        originating_claim={"projected_conversion_rate": 0.042},
        ranked_context=build_ranked_context_for_handoff(
            task="Validate CAC",
            originating_claim={"projected_conversion_rate": 0.042},
            extra_sources=[
                {
                    "source_id": "healthcare_hist",
                    "source_type": "org_context",
                    "label": "Hist",
                    "content": "historical healthcare conversion is only 2.6%",
                }
            ],
        ),
        originating_department="Marketing",
        receiving_department="Finance",
    )
    briefing = build_collaboration_briefing(handoff)
    assert_ranked_context_preserved(
        briefing,
        required_source_ids=["healthcare_hist", "originating_claim"],
        required_substrings=["2.6%"],
    )

    broken = dict(briefing)
    broken["collaboration"] = {**briefing["collaboration"], "ranked_context": []}
    with pytest.raises(AssertionError, match="lost ranked_context"):
        assert_ranked_context_preserved(broken, required_substrings=["2.6%"])


def test_parse_receiver_stance_challenge():
    assert (
        parse_receiver_stance(
            {
                "stance": "challenge",
                "reasoning": "Historical healthcare conversion is 2.6%, not 4.2%",
                "assumptions_challenged": ["conversion_rate"],
            }
        )
        == "challenge"
    )


def test_observability_surfaces_marketing_finance_label():
    events = [
        {
            "action": "agent.collaboration.receiver.completed",
            "created_at": "2026-09-03T20:00:00Z",
            "metadata": {
                "from_agent_id": "mkt",
                "to_agent_id": "fin",
                "from_department": "Marketing",
                "to_department": "Finance",
                "label": "Marketing → Finance",
                "stance": "challenge",
                "disagreement_visible": True,
                "chain_of_thought": "SECRET",
            },
        }
    ]
    rows = _handoffs_from_audit(events)
    assert len(rows) == 1
    assert rows[0]["label"] == "Marketing → Finance"
    assert rows[0]["stance"] == "challenge"
    assert rows[0]["disagreementVisible"] is True
    assert "chain_of_thought" not in rows[0]["metadata"]


def test_capability_resolution_reuses_ontology_not_second_layer():
    handoff = CollaborationTaskHandoff(
        originating_agent_id="mkt",
        receiving_agent_id="fin",
        task="Budget check",
        response_contract=CollaborationResponseContract(
            proposed_capability_id="email.send",
        ),
        connected_integrations=["gmail"],
    )
    resolution = resolve_proposed_capability(handoff, {})
    assert resolution is not None
    assert resolution["capability_id"] == "email.send"
    assert "react_write_gate" in resolution["note"]


def test_write_authority_uses_catalog_sot():
    with patch(
        "app.services.catalog_write_authority.invoke_action_requires_write_approval",
        return_value=True,
    ) as mocked:
        result = evaluate_write_authority_for_proposed_action(
            resolved_action="gmail.messages.send",
        )
    mocked.assert_called_once_with("gmail.messages.send")
    assert result["requires_write_approval"] is True
    assert result["path"].startswith("catalog_write_authority")


@pytest.mark.asyncio
async def test_finance_challenges_marketing_cac_trail():
    """Live-pattern scenario: Finance challenges Marketing's 4.2% vs 2.6% CAC assumption."""
    settings = SimpleNamespace()
    marketing = {
        "id": "mkt",
        "name": "Marketing Agent",
        "department": "Marketing",
        "status": "active",
    }
    finance = {
        "id": "fin",
        "name": "Finance Agent",
        "department": "Finance",
        "status": "active",
    }

    def _get_agent(_client, _org_id: str, agent_id: str):
        return {"mkt": marketing, "fin": finance}.get(agent_id)

    handoffs_insert = MagicMock()
    handoffs_insert.execute.return_value = MagicMock(
        data=[{"id": "handoff-cac-1", "from_agent_id": "mkt", "to_agent_id": "fin"}]
    )
    handoffs_table = MagicMock()
    handoffs_table.insert.return_value = handoffs_insert
    handoffs_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    mock_client = MagicMock()
    mock_client.table.side_effect = (
        lambda name: handoffs_table if name == "agent_handoffs" else MagicMock()
    )

    receiver_output = {
        "summary": "Challenge: conversion assumption invalid",
        "decision": {
            "stance": "challenge",
            "reasoning": (
                "Marketing's projected CAC assumes a 4.2% conversion rate; "
                "historical healthcare conversion is only 2.6%."
            ),
            "assumptions_challenged": ["projected_conversion_rate"],
            "recommendation": "Recalculate CAC at 2.6% before budget approval",
        },
        "confidence": 92,
    }
    reconcile_output = {
        "summary": "Revised claim",
        "decision": {
            "stance": "revise",
            "reasoning": "Accepted Finance challenge on conversion rate",
            "revised_claim": {"projected_conversion_rate": 0.026},
            "accepted_challenges": ["projected_conversion_rate"],
            "unresolved_disagreements": [],
        },
    }

    ranked = build_ranked_context_for_handoff(
        task="Review Marketing CAC projection before budget approval",
        originating_claim={
            "claim": "Projected CAC assumes a 4.2% conversion rate",
            "projected_conversion_rate": 0.042,
            "channel": "healthcare paid search",
        },
        extra_sources=[
            {
                "source_id": "healthcare_hist",
                "source_type": "org_context",
                "label": "Historical healthcare conversion",
                "score": 0.98,
                "content": "Historical healthcare conversion is only 2.6%",
            }
        ],
    )

    handoff = CollaborationTaskHandoff(
        originating_agent_id="mkt",
        receiving_agent_id="fin",
        task="Review Marketing CAC projection before budget approval",
        originating_claim={
            "claim": "Projected CAC assumes a 4.2% conversion rate",
            "projected_conversion_rate": 0.042,
        },
        ranked_context=ranked,
        originating_department="Marketing",
        receiving_department="Finance",
        workflow_run_id="run-cac-1",
    )

    # Mutation proof: if ranked context stripped, helper fails before execution.
    briefing_ok = build_collaboration_briefing(handoff)
    assert_ranked_context_preserved(
        briefing_ok,
        required_source_ids=["healthcare_hist"],
        required_substrings=["2.6%", "4.2"],
    )
    mutated = dict(briefing_ok)
    mutated["collaboration"] = {
        **briefing_ok["collaboration"],
        "ranked_context": [
            item
            for item in briefing_ok["collaboration"]["ranked_context"]
            if item.get("source_id") != "healthcare_hist"
        ],
    }
    with pytest.raises(AssertionError, match="healthcare_hist"):
        assert_ranked_context_preserved(
            mutated,
            required_source_ids=["healthcare_hist"],
            required_substrings=["2.6%"],
        )

    with patch("app.services.agent_collaboration_service.get_agent", side_effect=_get_agent):
        with patch(
            "app.services.agent_collaboration_service.run_agent_task",
            new_callable=AsyncMock,
            side_effect=[receiver_output, reconcile_output],
        ) as run_task:
            with patch("app.services.agent_collaboration_service.write_audit_event") as audit:
                with patch("app.services.handoff_service.write_audit_event"):
                    trail = await execute_internal_collaboration_handoff(
                        settings,
                        org_id="org-1",
                        actor_id="user-1",
                        handoff=handoff,
                        client=mock_client,
                    )

    assert trail.label == "Marketing → Finance"
    assert trail.receiver_stance == "challenge"
    assert trail.disagreement_visible is True
    assert "2.6%" in str(trail.receiver_response.get("reasoning") or "")
    assert trail.originator_reconciliation.get("stance") == "revise"
    assert COLLAB_AUDIT_CREATED in trail.audit_actions
    assert COLLAB_AUDIT_RECEIVER in trail.audit_actions
    assert COLLAB_AUDIT_RECONCILED in trail.audit_actions
    assert run_task.await_count == 2
    # Receiver then originator — feedback into originating agent, not standalone terminate.
    assert run_task.await_args_list[0].kwargs["agent"]["id"] == "fin"
    assert run_task.await_args_list[1].kwargs["agent"]["id"] == "mkt"
    # Briefing passed to receiver must preserve ranked context (Class A: shared path).
    receiver_briefing = run_task.await_args_list[0].kwargs["briefing"]
    assert_ranked_context_preserved(
        receiver_briefing,
        required_source_ids=["healthcare_hist"],
        required_substrings=["2.6%"],
    )
    audit_actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert COLLAB_AUDIT_CREATED in audit_actions
    assert COLLAB_AUDIT_RECEIVER in audit_actions
    assert COLLAB_AUDIT_RECONCILED in audit_actions


def test_extract_receiver_payload_from_summary_challenge():
    payload = extract_receiver_payload(
        {
            "summary": 'Finance response {"stance":"challenge","reasoning":"rates differ"}',
            "confidence": 80,
        }
    )
    assert payload["stance"] == "challenge"
