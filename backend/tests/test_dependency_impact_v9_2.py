from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dependency_impact_service import (
    ENTITY_WORKFLOW,
    SCHEDULE_SCOPE_NOTE,
    DependencyImpactService,
)


@pytest.mark.asyncio
async def test_attaches_next_run_time_to_dependents():
    service = DependencyImpactService(settings=MagicMock())
    items = [
        {
            "entityType": ENTITY_WORKFLOW,
            "entityId": "wf-soon",
            "label": "Soon",
            "relationship": "workflows.nodes references agent",
            "source": {},
        },
        {
            "entityType": ENTITY_WORKFLOW,
            "entityId": "wf-later",
            "label": "Later",
            "relationship": "workflows.nodes references agent",
            "source": {},
        },
    ]

    async def _schedule(org_id: str, workflow_id: str):
        if workflow_id == "wf-soon":
            return {"next_run_at": "2026-06-08T10:00:00+00:00"}
        if workflow_id == "wf-later":
            return {"next_run_at": "2026-06-09T10:00:00+00:00"}
        return None

    with patch.object(service, "_get_active_schedule", new=AsyncMock(side_effect=_schedule)):
        enriched = await service._attach_next_run_times("org-1", items)
    assert enriched[0]["entityId"] == "wf-soon"
    assert enriched[0]["nextScheduledRun"] == "2026-06-08T10:00:00+00:00"
    assert enriched[0]["willFailAtNextRun"] is True


@pytest.mark.asyncio
async def test_manual_only_workflows_marked_explicitly():
    service = DependencyImpactService(settings=MagicMock())
    items = [
        {
            "entityType": ENTITY_WORKFLOW,
            "entityId": "wf-manual",
            "label": "Manual only",
            "relationship": "workflow_nodes.connector_id FK",
            "source": {},
        }
    ]
    with patch.object(service, "_get_active_schedule", new=AsyncMock(return_value=None)):
        enriched = await service._attach_next_run_times("org-1", items)
    assert enriched[0]["nextScheduledRun"] is None
    assert enriched[0]["willFailAtNextRun"] is False


@pytest.mark.asyncio
async def test_sorted_soonest_first():
    service = DependencyImpactService(settings=MagicMock())
    items = [
        {"entityType": ENTITY_WORKFLOW, "entityId": "wf-b", "source": {}},
        {"entityType": ENTITY_WORKFLOW, "entityId": "wf-a", "source": {}},
    ]

    async def _schedule(org_id: str, workflow_id: str):
        mapping = {
            "wf-a": {"next_run_at": "2026-06-08T08:00:00+00:00"},
            "wf-b": {"next_run_at": "2026-06-08T12:00:00+00:00"},
        }
        return mapping.get(workflow_id)

    with patch.object(service, "_get_active_schedule", new=AsyncMock(side_effect=_schedule)):
        enriched = await service._attach_next_run_times("org-1", items)
    assert [row["entityId"] for row in enriched] == ["wf-a", "wf-b"]


def test_scope_note_discloses_schedule_limitation():
    from app.services.dependency_impact_service import build_scope_note

    note = build_scope_note()
    assert "scheduled triggers only" in note
    assert "manual runs" in note


def test_no_simulation_language_in_attach_method():
    import inspect

    from app.services.dependency_impact_service import DependencyImpactService

    source = inspect.getsource(DependencyImpactService._attach_next_run_times)
    assert "simulate" not in source.lower()


def test_no_two_hop_reasoning_introduced():
    import inspect

    from app.services import dependency_impact_service as module

    source = inspect.getsource(module.DependencyImpactService)
    assert "_find_one_hop_further" in source
    assert "_find_two_hop" not in source
    assert "two-hop" not in source.lower() or "one-hop" in source.lower()


def test_no_financial_impact_attempted():
    from app.services.dependency_impact_service import SCOPE_NOTE_BASE

    assert "financial" in SCOPE_NOTE_BASE
    assert "estimate" in SCOPE_NOTE_BASE.lower()
