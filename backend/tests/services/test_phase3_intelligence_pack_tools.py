"""Phase 3 unit tests — FRED/NVD invoke executors + HubSpot CRM outcome mapping."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.hubspot_trigger_service import map_hubspot_event_to_crm_outcome, maybe_emit_crm_outcome_from_hubspot_event
from app.services.intelligence_pack_tools import (
    INTELLIGENCE_PACK_TOOL_EXECUTORS,
    _exec_fred_series_get,
    _exec_nvd_cve_get,
)
from app.services.tool_types import ToolContext, ToolValidationError


def _ctx(**kwargs) -> ToolContext:
    settings = SimpleNamespace(
        fred_api_key=kwargs.pop("fred_api_key", "test-key"),
        nvd_api_key="",
        opencorporates_license_confirmed=False,
    )
    return ToolContext(
        settings=settings,
        client=kwargs.pop("client", MagicMock()),
        org_id=kwargs.pop("org_id", "org-1"),
        actor_id="actor-1",
        **kwargs,
    )


def test_fred_and_nvd_actions_registered():
    assert "fred.series.get" in INTELLIGENCE_PACK_TOOL_EXECUTORS
    assert "nvd.cve.get" in INTELLIGENCE_PACK_TOOL_EXECUTORS


def test_fred_missing_key_fail_closed(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    ctx = _ctx(fred_api_key="")
    with pytest.raises(ToolValidationError) as exc:
        _exec_fred_series_get(ctx, {"series_id": "GDP"})
    assert exc.value.code == "GRAVITREE_SOURCE_UNAVAILABLE"


def test_fred_happy_path(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    raw = {
        "ok": True,
        "vendor": "fred",
        "auth_mode": "gravitree_managed",
        "data": [{"date": "2024-01-01", "value": "100"}],
        "provenance": {"series_id": "GDP", "source": "fred"},
    }
    ingested = {
        "ok": True,
        "vendor": "fred",
        "cache": {"id": "cache-1"},
        "entities": [{"id": "ent-1"}],
        "signals": [{"id": "sig-1"}],
    }
    ctx = _ctx()
    with (
        patch("app.intelligence_packs.executive.sources.fetch_fred_series", return_value=raw) as fetch,
        patch("app.services.intelligence_pack_tools._run_async", side_effect=lambda c: raw),
        patch("app.services.intelligence_pack_tools.run_shared_ingestion", return_value=ingested) as pipe,
    ):
        result = _exec_fred_series_get(ctx, {"series_id": "GDP"})
    assert result.success is True
    assert result.action == "fred.series.get"
    assert result.data["ingestion"]["cache"]["id"] == "cache-1"
    pipe.assert_called_once()
    assert pipe.call_args.kwargs["vendor"] == "fred"


def test_nvd_requires_cve_id():
    ctx = _ctx()
    with pytest.raises(ToolValidationError) as exc:
        _exec_nvd_cve_get(ctx, {})
    assert exc.value.code == "NVD_CVE_REQUIRED"


def test_nvd_happy_path():
    raw = {
        "ok": True,
        "vendor": "nvd",
        "auth_mode": "gravitree_managed",
        "data": {"vulnerabilities": [{"cve": {"id": "CVE-2024-21762"}}]},
        "provenance": {"cve": "CVE-2024-21762", "source": "nvd"},
    }
    ingested = {
        "ok": True,
        "vendor": "nvd",
        "cache": {"id": "cache-nvd"},
        "entities": [{"id": "ent-nvd"}],
        "signals": [{"id": "sig-nvd"}],
    }
    ctx = _ctx()
    with (
        patch("app.services.intelligence_pack_tools._run_async", side_effect=lambda c: raw),
        patch("app.services.intelligence_pack_tools.run_shared_ingestion", return_value=ingested),
    ):
        result = _exec_nvd_cve_get(ctx, {"cve_id": "CVE-2024-21762"})
    assert result.success is True
    assert result.data["cve_id"] == "CVE-2024-21762"


def test_hubspot_maps_closedwon_only():
    event = {
        "subscriptionType": "deal.propertyChange",
        "propertyName": "dealstage",
        "propertyValue": "closedwon",
        "objectId": 99,
        "portalId": 1,
    }
    normalized = {"deal": {"id": "99", "properties": {"dealstage": "closedwon"}}}
    mapped = map_hubspot_event_to_crm_outcome(event, normalized)
    assert mapped == {"outcome_type": "won", "external_record_id": "99"}


def test_hubspot_skips_ambiguous_stage():
    event = {
        "subscriptionType": "deal.propertyChange",
        "propertyName": "dealstage",
        "propertyValue": "appointmentscheduled",
        "objectId": 99,
    }
    assert map_hubspot_event_to_crm_outcome(event, {"deal": {"id": "99"}}) is None


def test_maybe_emit_calls_ingest():
    client = MagicMock()
    event = {
        "subscriptionType": "deal.propertyChange",
        "propertyName": "dealstage",
        "propertyValue": "closedlost",
        "objectId": "deal-1",
        "portalId": 7,
    }
    normalized = {"deal": {"id": "deal-1"}}
    with patch(
        "app.services.crm_outcome_capture_service.ingest_crm_recommendation_outcome",
        return_value={"stored": True, "id": "out-1", "outcomeType": "lost"},
    ) as ingest:
        result = maybe_emit_crm_outcome_from_hubspot_event(
            client, org_id="org-1", event=event, normalized=normalized
        )
    assert result["outcomeType"] == "lost"
    ingest.assert_called_once()
    assert ingest.call_args.kwargs["outcome_type"] == "lost"
    assert ingest.call_args.kwargs["connector_type"] == "hubspot"
