"""Tests for SpecialistReasoningEngine."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.specialist_reasoning_engine import SpecialistReasoningEngine


def test_build_modifier_includes_department_kpis():
    engine = SpecialistReasoningEngine(settings=MagicMock())
    modifier = engine.build_modifier(
        {"department": "sales", "name": "Sales Agent"},
        {"intent": "analysis"},
        business_signals=[{"title": "Pipeline coverage low"}],
    )
    assert "win rate" in modifier.lower()
    assert "Pipeline coverage low" in modifier


def test_enrich_classification_sets_department():
    engine = SpecialistReasoningEngine(settings=MagicMock())
    enriched = engine.enrich_classification({"intent": "analysis"}, {"department": "marketing"})
    assert enriched["department"] == "marketing"
    assert enriched["specialist_persona"]
