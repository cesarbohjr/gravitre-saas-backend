"""Tests for Wave 7 execution confidence extensions."""
from __future__ import annotations

from app.services.execution_confidence_engine import ExecutionConfidenceEngine


def test_assess_connector_readiness_when_not_connected():
    engine = ExecutionConfidenceEngine()
    result = engine.assess_connector_readiness(connector="hubspot", connected=False)
    assert result["ready"] is False
    assert result["confidence_penalty"] > 0


def test_assess_connector_readiness_when_connected():
    engine = ExecutionConfidenceEngine()
    result = engine.assess_connector_readiness(connector="hubspot", connected=True, chat_executable=True)
    assert result["ready"] is True
    assert result["confidence_penalty"] == 0.0


def test_assess_execution_gate_blocks_low_confidence_with_approval():
    engine = ExecutionConfidenceEngine()
    gate = engine.assess_execution_gate(
        pre_confidence={"confidence": 0.45},
        risk_evaluation={"requires_approval": True},
        connector_readiness={"ready": False, "reason": "hubspot not connected", "confidence_penalty": 0.15},
    )
    assert gate["requires_approval"] is True
    assert gate["can_proceed"] is False
    assert "hubspot" in gate["reason"].lower() or "not connected" in gate["reason"].lower()
