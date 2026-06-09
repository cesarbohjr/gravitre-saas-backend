"""Tests for Meson interpret + deploy service (STA-161)."""
from __future__ import annotations

import pytest

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
