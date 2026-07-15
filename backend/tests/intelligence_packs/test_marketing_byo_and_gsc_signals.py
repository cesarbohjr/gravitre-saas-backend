"""SEMrush/Ahrefs BYO labeling + GSC Marketing PackSignal."""
from __future__ import annotations

import pytest

from app.connectors.seo_byo_capability import (
    AHREFS_REQUIREMENT_NOTE,
    SEMRUSH_REQUIREMENT_NOTE,
    byo_seo_requirement_note,
)
from app.intelligence_packs.shared.auth_mode import AuthMode, get_auth_mode, resolve_credential_source
from app.intelligence_packs.shared.mappers import (
    map_google_search_console,
    register_builtin_mappers_and_signals,
)
from app.intelligence_packs.shared.signals import evaluate_pack_signals, registered_signals
from app.intelligence_packs.shared.kpis import PACK_VENDOR_MAP


@pytest.mark.parametrize("vendor", ["semrush", "ahrefs"])
def test_seo_vendors_are_byo_required(vendor: str):
    assert get_auth_mode(vendor) == AuthMode.BYO_REQUIRED
    result = resolve_credential_source(
        vendor,
        org_has_secret=False,
        platform_env_present=True,
    )
    assert result["ok"] is False
    assert result["error_code"] == "BYO_CREDENTIAL_REQUIRED"


def test_seo_byo_requirement_notes():
    assert "SEMrush" in (byo_seo_requirement_note("semrush") or "")
    assert "Ahrefs" in (byo_seo_requirement_note("ahrefs") or "")
    assert "shared" in SEMRUSH_REQUIREMENT_NOTE.lower()
    assert "shared" in AHREFS_REQUIREMENT_NOTE.lower()


def test_gsc_mapper_and_signal_page_aggregates_only():
    register_builtin_mappers_and_signals()
    assert "gsc.page_performance_rollup" in registered_signals()
    assert PACK_VENDOR_MAP["marketing-intelligence-pack"] == ("google_search_console",)

    raw = {
        "ok": True,
        "auth_mode": "customer_owned",
        "data": {
            "dimensions": ["page"],
            "siteUrl": "sc-domain:gravitre.app",
            "rows": [
                {"page": "https://gravitre.app/", "clicks": 12, "impressions": 100, "position": 4.2},
            ],
        },
        "provenance": {"site_url": "sc-domain:gravitre.app"},
    }
    records = map_google_search_console(raw)  # type: ignore[arg-type]
    assert len(records) == 1
    assert records[0]["vendor"] == "google_search_console"
    assert records[0]["payload"]["total_clicks"] == 12
    assert records[0]["payload"]["includes_raw_queries"] is False
    hits = evaluate_pack_signals(records[0])
    assert len(hits) == 1
    assert hits[0]["signal_definition_id"] == "gsc.page_performance_rollup"
    assert "query" not in (hits[0].get("payload") or {})


def test_gsc_mapper_strips_raw_query_dimension():
    register_builtin_mappers_and_signals()
    raw = {
        "ok": True,
        "auth_mode": "customer_owned",
        "data": {
            "dimensions": ["query"],
            "rows": [{"query": "cesar email@x.com", "clicks": 1, "impressions": 3}],
        },
        "provenance": {},
    }
    records = map_google_search_console(raw)  # type: ignore[arg-type]
    assert records[0]["payload"]["includes_raw_queries"] is False
    assert "cesar" not in str(records[0]["payload"])
    hits = evaluate_pack_signals(records[0])
    # No page aggregates remain after strip → no signal
    assert hits == []
