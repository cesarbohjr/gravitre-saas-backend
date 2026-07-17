"""Tests for Operational Intelligence Layer patterns (fail-open wiring)."""
from __future__ import annotations

from app.services.context_distiller import distill_text
from app.services.context_registry import plan_context_registry
from app.services.operational_intelligence_layer import get_operational_intelligence_layer
from app.services.operational_intelligence_patterns import (
    OPERATIONAL_INTELLIGENCE_PATTERNS,
    pattern_coverage_summary,
)
from app.services.predictive_context_loader import adjust_registry_plan_for_prediction
from app.services.reflection_loop_service import ReflectionLoopService
from app.services.self_healing_advisor import advise_self_heal, classify_failure
from app.services.tool_result_summarizer import summarize_tool_payload
from app.services.working_memory_profile import build_working_memory_profile


def test_pattern_catalog_covers_fifteen_plus_layer():
    assert len(OPERATIONAL_INTELLIGENCE_PATTERNS) >= 16
    coverage = pattern_coverage_summary()
    assert coverage["patternCount"] >= 16
    assert coverage["counts"]["live"] + coverage["counts"]["partial"] >= 15


def test_predictive_context_expands_on_low_confidence():
    base = plan_context_registry(
        query="pipeline?",
        classification={"intent": "knowledge_lookup", "classification_confidence": 0.3},
        routing_tier="multi_step",
    )
    adjusted = adjust_registry_plan_for_prediction(
        base,
        classification={"intent": "knowledge_lookup", "classification_confidence": 0.3},
        query="pipeline?",
    )
    assert adjusted.rag_top_k >= base.rag_top_k
    assert "signals" in adjusted.enabled_slices
    assert any("predictive_low_confidence" in r for r in adjusted.reasons)


def test_working_memory_profile_has_ltm_stm_scratchpad():
    profile = build_working_memory_profile(
        conversation_memory={"preferences": ["prefer concise"], "rejections": []},
        task_state={
            "current_plan": {"objective": "Close Q3 pipeline gaps"},
            "pending_steps": ["pull deals"],
            "active_entities": ["Acme"],
        },
        org_context_block="Acme Corp MSP",
        query="Show stale deals",
    )
    data = profile.to_dict()
    assert data["long_term"]["user_profile"]["preferences"]
    assert data["short_term"]["current_objective"]
    assert "Acme" in data["scratchpad"]["active_entities"]
    assert "Long-term" in profile.prompt_section() or "Short-term" in profile.prompt_section()


def test_context_distiller_compresses_large_text():
    blob = ("The quarterly pipeline review found risk. " * 80) + "Acme Corp missed renewal."
    result = distill_text(blob, max_chars=400, label="pipeline")
    assert result["distilled"] is True
    assert len(result["content"]) <= 400
    assert result["key_findings"]


def test_tool_result_summarizer_aggregates_large_lists():
    contacts = [
        {"id": str(i), "properties": {"firstname": f"User{i}", "lastname": "Test", "email": f"u{i}@x.com"}}
        for i in range(40)
    ]
    summary = summarize_tool_payload({"contacts": contacts}, action="hubspot.contacts.list")
    assert summary["truncated"] is True
    assert summary["record_count"] == 40
    assert "40" in summary["summary"]
    assert len(summary["insights"]) <= 12


def test_reflection_loop_flags_low_confidence():
    decision = ReflectionLoopService().evaluate(
        critic={"passed": True, "issues": []},
        confidence={"score": 0.2},
        tool_results=[],
    )
    assert decision["should_revise"] is True
    assert "retrieve_more" in decision["actions"]


def test_self_heal_permission_and_backup():
    assert classify_failure("403 missing scope tickets") == "permission"
    advice = advise_self_heal(
        tool_results=[{"success": False, "tool": "hubspot.tickets.get", "error": "403 forbidden"}],
        connected_integrations=["hubspot", "salesforce"],
    )
    assert advice["hasFailures"] is True
    assert advice["advisoryOnly"] is True
    steps = advice["suggestions"][0]["steps"]
    assert any(s.get("type") == "reconnect" for s in steps)
    assert any(s.get("type") == "backup_connector" for s in steps)


def test_operational_intelligence_layer_fail_open_envelope():
    oil = get_operational_intelligence_layer()
    envelope = oil.build_operational_envelope(
        what_happened="test",
        why="unit",
        action=[],
        outcome={"ok": True},
        confidence={"score": 0.7},
    )
    assert envelope["whatHappened"] == "test"
    assert envelope["coverage"]["patternCount"] >= 16
    catalog = oil.catalog()
    assert len(catalog["patterns"]) >= 16
