"""CISA + SEC EDGAR follow-on invoke unit tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.intelligence_packs.shared.mappers import (
    map_cisa_kev,
    map_sec_edgar,
    register_builtin_mappers_and_signals,
)
from app.intelligence_packs.shared.pipeline import ensure_plumbing_registered
from app.intelligence_packs.shared.schemas import ok_result
from app.services.intelligence_pack_tools import INTELLIGENCE_PACK_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def setup_module():
    ensure_plumbing_registered()
    register_builtin_mappers_and_signals()


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(fred_api_key="", nvd_api_key="", sec_user_agent="Gravitre research@gravitre.ai"),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )


def test_cisa_and_sec_actions_registered():
    registered = set(list_registered_actions())
    assert "cisa_kev.feed.get" in registered
    assert "sec_edgar.filings.search" in registered


def test_map_cisa_kev():
    raw = ok_result(
        "cisa_kev",
        auth_mode="gravitree_managed",
        data={"count": 2, "sample": [{"cveID": "CVE-2024-1", "vulnerabilityName": "Example"}]},
    )
    rows = map_cisa_kev(raw)
    assert rows[0]["vendor"] == "cisa_kev"
    assert rows[0]["signal_hints"]["kev_entries_present"] is True


def test_map_sec_edgar():
    raw = ok_result(
        "sec_edgar",
        auth_mode="gravitree_managed",
        data=[{"title": "Microsoft 10-K", "form": "10-K"}],
        provenance={"query": "Microsoft"},
    )
    rows = map_sec_edgar(raw)
    assert rows[0]["vendor"] == "sec_edgar"
    assert rows[0]["signal_hints"]["filings_found"] is True


@patch("app.services.intelligence_pack_tools.run_shared_ingestion")
@patch("app.services.intelligence_pack_tools._run_async")
def test_exec_cisa_kev_feed_get(mock_async, mock_ingest):
    mock_async.return_value = ok_result(
        "cisa_kev",
        auth_mode="gravitree_managed",
        data={"count": 1, "sample": [{"cveID": "CVE-2024-1"}]},
    )
    mock_ingest.return_value = {"cache": {"id": "c1"}, "entities": [], "signals": []}
    result = INTELLIGENCE_PACK_TOOL_EXECUTORS["cisa_kev.feed.get"](_ctx(), {})
    assert result.success is True
    assert result.data.get("count") == 1


@patch("app.services.intelligence_pack_tools.run_shared_ingestion")
@patch("app.services.intelligence_pack_tools._run_async")
def test_exec_sec_edgar_filings_search(mock_async, mock_ingest):
    mock_async.return_value = ok_result(
        "sec_edgar",
        auth_mode="gravitree_managed",
        data=[{"title": "MSFT 10-K", "form": "10-K"}],
        provenance={"query": "Microsoft"},
    )
    mock_ingest.return_value = {"cache": {"id": "s1"}, "entities": [], "signals": []}
    result = INTELLIGENCE_PACK_TOOL_EXECUTORS["sec_edgar.filings.search"](_ctx(), {"query": "Microsoft"})
    assert result.success is True
    assert result.data.get("query") == "Microsoft"
