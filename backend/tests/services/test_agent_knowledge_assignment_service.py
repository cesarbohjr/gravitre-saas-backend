"""Tests for AgentKnowledgeAssignmentService."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService


def test_resolve_assignments_from_agent_config():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    agent = {
        "id": "agent-1",
        "config": {
            "reference_folders": [{"id": "fld-1", "name": "Brand assets"}],
            "knowledge_packs": [{"id": "pack-1", "name": "Sales playbook"}],
        },
    }
    rows = service.resolve_assignments(agent)
    assert len(rows) == 2
    assert rows[0]["sourceType"] == "folder"
    assert rows[1]["sourceType"] == "knowledge_pack"


def test_build_prompt_section_lists_enabled_sources():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    section = service.build_prompt_section(
        [
            {"label": "Brand assets", "sourceType": "folder", "freshnessStatus": "fresh", "enabled": True},
        ]
    )
    assert "Brand assets" in section
    assert "freshness: fresh" in section
