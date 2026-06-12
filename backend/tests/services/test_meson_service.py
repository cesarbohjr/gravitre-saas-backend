"""Tests for Meson interpret + deploy service (STA-161)."""
from __future__ import annotations

import pytest

from unittest.mock import MagicMock

from app.services.meson_service import MesonService


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
        dismissed_ids={"add-approval"},
    )
    assert all(s.id != "add-approval" for s in result.suggestions)


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
