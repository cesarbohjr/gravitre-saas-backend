"""Tests for Tier 3 intelligence optimizations."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.artifact_registry_service import (
    get_artifact_registry_service,
    serialize_execution_result,
)
from app.services.context_prioritization_engine import ContextSource
from app.services.context_registry import filter_context_sources, plan_context_registry
from app.services.conversational_execution_service import ExecutionResult
from app.services.governed_codeact_service import GovernedCodeActError, get_governed_codeact_service
from app.services.pack_operational_state_service import (
    build_pack_operational_section,
    extract_pack_ids,
)
from app.operators.assistant_mode_config import resolve_assistant_tool_names


def test_extract_pack_ids_from_assignments():
    assignments = [
        {"metadata": {"intelligence_pack_id": "msp-intelligence-pack"}},
        {"metadata": {"intelligencePackId": "sales-intelligence-pack"}},
        {"metadata": {"intelligence_pack_id": "msp-intelligence-pack"}},
    ]
    assert extract_pack_ids(assignments) == [
        "msp-intelligence-pack",
        "sales-intelligence-pack",
    ]


def test_context_registry_enables_pack_state_slice():
    plan = plan_context_registry(
        query="Summarize MSP risk posture",
        classification={"intent": "analytics"},
        connected_integrations=[],
        knowledge_assignments=[
            {"metadata": {"intelligence_pack_id": "msp-intelligence-pack"}},
        ],
    )
    assert "pack_state" in plan.enabled_slices


def test_filter_context_sources_keeps_pack_state():
    plan = plan_context_registry(
        query="MSP signals",
        classification={"intent": "analytics"},
        connected_integrations=[],
        knowledge_assignments=[{"metadata": {"intelligence_pack_id": "msp-intelligence-pack"}}],
    )
    sources = [
        ContextSource("pack", "pack_state", "Pack state", 0.0, "kpi snapshot"),
        ContextSource("org", "org_context", "Org", 0.0, "org"),
    ]
    kept = filter_context_sources(sources, plan)
    assert any(s.source_type == "pack_state" for s in kept)


def test_build_pack_operational_section_without_client_errors():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    client.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    section = build_pack_operational_section(
        client,
        org_id="org-1",
        knowledge_assignments=[{"metadata": {"intelligence_pack_id": "msp-intelligence-pack"}}],
    )
    assert "pack_operational_state" in section
    assert "msp-intelligence-pack" in section


def test_governed_codeact_executes_transform():
    service = get_governed_codeact_service()
    payload = service.execute_transform(
        code="result = sorted(data.get('values', []))",
        inputs={"values": [3, 1, 2]},
        description="sort values",
    )
    assert payload["success"] is True
    assert payload["result"] == [1, 2, 3]


def test_governed_codeact_blocks_imports():
    service = get_governed_codeact_service()
    try:
        service.execute_transform(code="import os\nresult = 1", inputs={})
        raise AssertionError("expected GovernedCodeActError")
    except GovernedCodeActError as exc:
        assert "Imports" in str(exc)


def test_artifact_registry_builds_connector_and_document_cards():
    registry = get_artifact_registry_service()
    result = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="rec-1",
        title="Create HubSpot contact",
        body="Created contact Jane Doe",
        result_url="https://app.hubspot.com/contacts/1",
        integration="hubspot",
        structured={"format": "markdown", "title": "Brief", "content": "# Brief\nHello"},
    )
    artifacts = registry.build_artifacts(result)
    kinds = {row["kind"] for row in artifacts}
    assert "record" in kinds
    assert "document" in kinds
    record = next(row for row in artifacts if row["kind"] == "record")
    assert record.get("metadata", {}).get("external_url") == "https://app.hubspot.com/contacts/1"


def test_serialize_execution_result_attaches_artifacts():
    result = ExecutionResult(
        success=True,
        entity_type="run",
        entity_id="run-1",
        title="Workflow run started",
        body="Run queued",
        result_url="/runs/run-1",
        structured={"runId": "run-1", "workflowId": "wf-1", "status": "queued"},
    )
    payload = serialize_execution_result(result)
    assert payload.get("artifacts")
    assert payload["structured"]["artifacts"]


def test_reasoning_mode_includes_code_transform_tool():
    tools = resolve_assistant_tool_names("reasoning", None)
    assert "code_transform" in tools
