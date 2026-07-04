"""Tests for agent knowledge assignment filtering and sync rules."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService
from app.services.agent_knowledge_sync_service import AgentKnowledgeSyncService
from app.services.knowledge_source_types import validate_source_type
from app.marketplace.demo_workflow_templates import (
    get_agent_knowledge_demo_workflow,
    list_agent_knowledge_demo_workflows,
)


def test_validate_source_type_accepts_drive_folder():
    assert validate_source_type("google_drive_folder") == "google_drive_folder"
    assert validate_source_type("folder") == "google_drive_folder"


def test_filter_rag_sources_keeps_unassigned_with_lower_tier():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    assignments = [
        {"label": "Brand assets", "sourceId": "fld-1", "enabled": True},
    ]
    rag_sources = [
        {"title": "Brand assets / Q2 guide", "source": "Brand assets", "score": 0.9},
        {"title": "Unassigned HR doc", "source": "HR", "score": 0.8},
    ]
    filtered, missing = service.filter_rag_sources(rag_sources, assignments)
    assert len(filtered) == 2
    assert filtered[0]["match_tier"] in {"label_fallback", "source_id", "assignment_id"}
    assert any(row.get("match_tier") == "unassigned" for row in filtered)
    assert missing == []


def test_filter_rag_sources_strict_mode_excludes_unassigned():
    from app.services.domain_retrieval_policy import RetrievalPlan

    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    assignments = [{"label": "Sales playbook", "sourceId": "pack-1", "enabled": True}]
    plan = RetrievalPlan(active=True, strict_assignment_mode=True)
    filtered, missing = service.filter_rag_sources(
        [{"title": "Other doc", "source": "Other", "score": 0.5}],
        assignments,
        plan=plan,
    )
    assert filtered == []
    assert missing


def test_assigned_knowledge_gap_message_when_unassigned():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    message = service.assigned_knowledge_gap_message([], "What are our brand guidelines?")
    assert message
    assert "approved knowledge source" in message.lower()


def test_sync_rules_exclude_sensitive_names():
    sync = AgentKnowledgeSyncService(settings=MagicMock())
    assignment = {
        "excludeRules": ["legal"],
        "tagsExcluded": [],
        "tagsRequired": [],
        "includeRules": [],
        "freshnessPolicy": {},
    }
    assert sync.evaluate_rules(assignment, {"name": "Approved marketing brief", "tags": []}) is True
    assert sync.evaluate_rules(assignment, {"name": "Legal compensation policy", "tags": []}) is False


def test_demo_workflow_templates_load():
    workflows = list_agent_knowledge_demo_workflows()
    assert len(workflows) == 4
    stale = get_agent_knowledge_demo_workflow("demo-stale-deals")
    assert stale is not None
    assert stale["requiresApproval"] is False
    launch = get_agent_knowledge_demo_workflow("demo-launch-campaign")
    assert launch is not None
    assert launch["requiresApproval"] is True
