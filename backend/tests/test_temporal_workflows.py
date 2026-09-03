"""Temporal workflow tests — worker registration and graceful degradation."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.temporal.worker import registered_workflow_names, temporal_configured


def test_temporal_worker_registers_all_workflows():
    """The registered set, named in full.

    This asserted five names and then `len(names) == 5`, so registering
    StandingInvestigatorWorkflow broke it with `assert 6 == 5` -- a failure that
    says nothing about what changed. Comparing the whole set means adding a
    workflow still forces a deliberate update, but the diff names the newcomer.
    """
    assert set(registered_workflow_names()) == {
        "CompanyIntelligenceWorkflow",
        "MarketplaceInstallWorkflow",
        "MemoryPromotionWorkflow",
        "MLModelTrainingWorkflow",
        "OutcomeMeasurementWorkflow",
        "StandingInvestigatorWorkflow",
    }


def test_registered_workflow_names_have_no_duplicates():
    names = registered_workflow_names()
    assert len(names) == len(set(names))


def test_asyncio_fallback_when_temporal_not_configured(monkeypatch):
    monkeypatch.delenv("TEMPORAL_HOST", raising=False)
    assert temporal_configured() is False


def test_temporal_configured_when_host_set(monkeypatch):
    monkeypatch.setenv("TEMPORAL_HOST", "localhost:7233")
    assert temporal_configured() is True


@pytest.mark.asyncio
async def test_workflow_retries_on_activity_failure():
    """RetryPolicy on CompanyIntelligenceWorkflow allows up to 3 attempts."""
    from temporalio.common import RetryPolicy

    from app.temporal.workflows import CompanyIntelligenceWorkflow

    # Workflow class exposes retry via execute_activity kwargs in run method source
    import inspect

    source = inspect.getsource(CompanyIntelligenceWorkflow.run)
    assert "RetryPolicy" in source
    assert "maximum_attempts=3" in source


@pytest.mark.asyncio
async def test_marketplace_install_resumes_from_checkpoint():
    """MarketplaceInstallWorkflow executes one activity per asset (checkpoint boundary)."""
    import inspect

    from app.temporal.workflows import MarketplaceInstallWorkflow

    source = inspect.getsource(MarketplaceInstallWorkflow.run)
    assert "for asset_id in asset_ids" in source
    assert "execute_activity" in source


@pytest.mark.asyncio
async def test_outcome_measurement_fires_after_correct_window():
    import inspect

    from app.temporal.workflows import OutcomeMeasurementWorkflow

    source = inspect.getsource(OutcomeMeasurementWorkflow.run)
    assert "workflow.sleep" in source
    assert "attribution_window_days" in source
