"""Tests for Meson interpret + deploy service (STA-161/143)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.meson_service import MesonService, _merge_meson_preferences


@pytest.mark.asyncio
async def test_interpret_build_request_heuristic_fallback():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    result = await service.interpret_build_request(
        intent="Build a marketing nurture program for SMB leads",
        department="marketing",
        systems=["crm", "email"],
        output_types=["campaigns", "workflows"],
        org_id="org-1",
    )
    assert result.intent.startswith("Build a marketing")
    assert result.department == "marketing"
    assert result.generated_config.agent
    assert len(result.generated_config.training) >= 2
    assert result.generated_config.workflows
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_interpret_learns_preferences_when_client_provided():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.maybe_single.return_value = table
    table.execute.return_value = MagicMock(data=None)
    table.upsert.return_value = table
    client.table.return_value = table

    await service.interpret_build_request(
        intent="Build a sales follow-up agent",
        department="sales",
        systems=["crm"],
        output_types=["workflows"],
        org_id="org-1",
        user_id="user-1",
        client=client,
    )

    client.table.assert_any_call("meson_user_preferences")
    table.upsert.assert_called_once()


def test_merge_meson_preferences_tracks_counts():
    merged = _merge_meson_preferences(
        {},
        department="marketing",
        systems=["crm", "email"],
        output_types=["workflows"],
        event="interpret",
    )
    assert merged["department_counts"]["marketing"] == 1
    assert merged["system_counts"]["crm"] == 1
    assert merged["output_type_counts"]["workflows"] == 1
    assert merged["interpret_count"] == 1


def test_format_preferences_for_prompt():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    text = service.format_preferences_for_prompt(
        {
            "department_counts": {"marketing": 3},
            "system_counts": {"crm": 2, "email": 1},
            "output_type_counts": {"workflows": 4},
            "build_hour_counts": {"14": 2},
            "interpret_count": 5,
            "deploy_count": 1,
        }
    )
    assert "marketing" in text
    assert "crm" in text
    assert "workflows" in text


def test_get_user_preferences_response():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.maybe_single.return_value = table
    table.execute.return_value = MagicMock(
        data={
            "preferences": {
                "department_counts": {"sales": 2},
                "system_counts": {"crm": 3},
                "output_type_counts": {"workflows": 1},
                "build_hour_counts": {"9": 2},
                "interpret_count": 2,
                "deploy_count": 1,
            }
        }
    )
    client.table.return_value = table

    prefs = service.get_user_preferences(client, "org-1", "user-1")
    assert prefs.department == "sales"
    assert "crm" in prefs.systems
    assert prefs.interpret_count == 2
    assert prefs.deploy_count == 1


@pytest.mark.asyncio
async def test_interpret_maps_systems_and_outputs():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    result = await service.interpret_build_request(
        intent="Automate finance invoice follow-ups",
        department="finance",
        systems=["data"],
        output_types=["reports"],
        org_id="org-1",
    )
    assert result.systems == ["data"]
    assert "reports" in result.output_types
    assert result.generated_config.sample_outputs


def test_workflow_suggestions_heuristics():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    result = service.get_workflow_suggestions(
        workflow_state={
            "nodes": [
                {"type": "source", "name": "Ingest"},
                {"type": "agent", "name": "Process"},
            ]
        },
        last_added_node={"type": "agent"},
        org_id="org-1",
    )
    ids = {s.id for s in result.suggestions}
    assert "add-approval" in ids


def test_workflow_suggestions_respects_dismissed():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    result = service.get_workflow_suggestions(
        workflow_state={
            "nodes": [
                {"type": "source", "name": "Ingest"},
                {"type": "agent", "name": "Process"},
            ]
        },
        last_added_node={"type": "agent"},
        org_id="org-1",
        feedback_summary={"dismissed_ids": {"add-approval"}},
    )
    assert all(s.id != "add-approval" for s in result.suggestions)


def test_feedback_summary_and_metrics():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(
        data=[
            {
                "metadata": {
                    "suggestionId": "add-approval",
                    "action": "dismissed",
                    "workflowId": "wf-1",
                    "reason": "Not needed",
                }
            },
            {
                "metadata": {
                    "suggestionId": "add-slack",
                    "action": "accepted",
                    "workflowId": "wf-1",
                }
            },
            {
                "metadata": {
                    "suggestionId": "add-slack",
                    "action": "accepted",
                    "workflowId": "wf-1",
                }
            },
        ]
    )
    client.table.return_value = table

    summary = service.load_feedback_summary(client, "org-1", workflow_id="wf-1")
    assert "add-approval" in summary["dismissed_ids"]
    assert summary["by_suggestion"]["add-slack"]["accepted"] == 2

    metrics = service.get_feedback_metrics(client, "org-1", workflow_id="wf-1")
    assert metrics.accepted_count == 2
    assert metrics.dismissed_count == 1
    assert metrics.acceptance_rate == round(2 / 3, 3)


def test_rank_suggestions_boosts_accepted_patterns():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    result = service.get_workflow_suggestions(
        workflow_state={
            "nodes": [
                {"type": "source", "name": "Ingest"},
                {"type": "agent", "name": "Process"},
                {"type": "task", "name": "Transform"},
            ]
        },
        last_added_node={"type": "task"},
        org_id="org-1",
        feedback_summary={
            "dismissed_ids": set(),
            "by_suggestion": {"add-slack": {"accepted": 4, "dismissed": 0}},
        },
    )
    slack = next((s for s in result.suggestions if s.id == "add-slack"), None)
    assert slack is not None
    assert slack.confidence >= 0.79


def test_proactive_insights_default_when_empty(monkeypatch):
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=[])
    client.table.return_value = table
    monkeypatch.setattr(
        "app.services.meson_service.list_failure_alerts",
        lambda *_a, **_k: [],
    )
    result = service.get_proactive_insights(client, "org-1", environment_name="default")
    assert result.insights
    assert result.insights[0].id == "meson-ready"


def test_workflow_optimizations_draft_and_ready(monkeypatch):
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()

    def table_side_effect(name: str):
        t = MagicMock()
        t.select.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t
        t.order.return_value = t
        if name == "workflow_defs":
            t.execute.return_value = MagicMock(
                data=[{"id": "wf-1", "name": "Follow-up", "status": "draft", "stage": "dev"}]
            )
        else:
            t.execute.return_value = MagicMock(data=[])
        return t

    client.table.side_effect = table_side_effect
    monkeypatch.setattr(
        "app.services.meson_service.list_failure_alerts",
        lambda *_a, **_k: [],
    )

    result = service.get_workflow_optimizations(
        client,
        "org-1",
        "wf-1",
        environment_name="default",
    )
    ids = {i.id for i in result.insights}
    assert "publish-this-workflow" in ids


def test_workflow_optimizations_not_found():
    service = MesonService(model_router=object())  # type: ignore[arg-type]
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=[])
    client.table.return_value = table

    result = service.get_workflow_optimizations(
        client,
        "org-1",
        "missing-wf",
        environment_name="default",
    )
    assert result.insights[0].id == "workflow-not-found"
