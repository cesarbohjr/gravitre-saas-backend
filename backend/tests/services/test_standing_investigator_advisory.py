"""Standing investigators are advisory-only and never auto-execute writes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.standing_investigator_service import StandingInvestigatorService


@pytest.mark.asyncio
async def test_disabled_setting_skips_investigation():
    svc = StandingInvestigatorService(settings=MagicMock())
    with patch.object(svc, "is_enabled", new_callable=AsyncMock, return_value=False):
        result = await svc.run_investigation_for_org("org-1")
    assert result["status"] == "disabled"
    assert result["advisory_only"] is True
    assert result["writes_executed"] is False


@pytest.mark.asyncio
async def test_investigation_advisory_never_writes_connectors():
    svc = StandingInvestigatorService(settings=MagicMock())
    findings = [
        {
            "finding_type": "failed_workflow_runs",
            "title": "2 failed workflow run(s) today",
            "body": "advisory",
            "evidence": {"count": 2, "advisory_only": True},
        }
    ]
    with (
        patch.object(svc, "is_enabled", new_callable=AsyncMock, return_value=True),
        patch.object(svc, "_collect_read_scoped_findings", new_callable=AsyncMock, return_value=findings),
        patch.object(svc, "_persist_findings", return_value=findings),
        patch.object(svc, "_notify_admins", return_value=1),
    ):
        result = await svc.run_investigation_for_org("org-1")

    assert result["advisory_only"] is True
    assert result["writes_executed"] is False
    assert result["finding_count"] == 1
    assert result["admins_notified"] == 1
